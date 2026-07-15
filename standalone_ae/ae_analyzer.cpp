#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include <mutex>
#include <deque>
#include <thread>
#include <chrono>
#include <algorithm>

class AeAnalyzer : public rclcpp::Node {
public:
  AeAnalyzer() : Node("ae_analyzer") {
    // Match the publisher's default QoS (Reliable, Volatile, Depth 10)
    sub_ = this->create_subscription<sensor_msgs::msg::Image>(
      "/siyi/image_raw", 10,
      std::bind(&AeAnalyzer::image_cb, this, std::placeholders::_1)
    );
    frame_count_ = 0;
  }

  void image_cb(const sensor_msgs::msg::Image::SharedPtr msg) {
    if (frame_count_ == 0) {
      RCLCPP_INFO(this->get_logger(), "Success: First image received on topic '/siyi/image_raw'!");
    }
    frame_count_++;

    try {
      cv_bridge::CvImagePtr cv_ptr = cv_bridge::toCvCopy(msg, "bgr8");
      if (!cv_ptr || cv_ptr->image.empty()) {
        RCLCPP_WARN(this->get_logger(), "Received empty or invalid image frame.");
        return;
      }
      
      std::lock_guard<std::mutex> lock(mutex_);
      // Deep copy to ensure memory stability
      latest_frame_ = cv_ptr->image.clone();
      frame_ready_ = true;
    } catch (cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
    }
  }

  bool get_latest_frame(cv::Mat& frame) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (frame_ready_ && !latest_frame_.empty()) {
      frame = latest_frame_.clone();
      frame_ready_ = false;
      return true;
    }
    return false;
  }

  int get_frame_count() const {
    return frame_count_;
  }

private:
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
  cv::Mat latest_frame_;
  bool frame_ready_{false};
  std::mutex mutex_;
  int frame_count_;
};

int main(int argc, char** argv) {
  // Force X11 backend to prevent Wayland crashes
  setenv("QT_QPA_PLATFORM", "xcb", 1);
  setenv("XDG_SESSION_TYPE", "x11", 1);
  setenv("GDK_BACKEND", "x11", 1);

  rclcpp::init(argc, argv);
  auto node = std::make_shared<AeAnalyzer>();

  // Spin ROS2 in a background thread
  std::thread spin_thread([node]() {
    rclcpp::spin(node);
  });

  std::deque<double> history;
  auto t_start = std::chrono::steady_clock::now();

  cv::namedWindow("SIYI A8 - C++ AE Analyzer", cv::WINDOW_AUTOSIZE);

  RCLCPP_INFO(node->get_logger(), "Subscribed to '/siyi/image_raw'. Waiting for first frame...");

  while (rclcpp::ok()) {
    cv::Mat frame;
    if (node->get_latest_frame(frame)) {
      if (frame.empty()) {
        continue;
      }

      cv::Mat gray;
      cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
      
      if (gray.empty()) {
        continue;
      }

      double mean_brightness = cv::mean(gray)[0];

      auto t_now = std::chrono::steady_clock::now();
      double elapsed = std::chrono::duration<double>(t_now - t_start).count();
      history.push_back(mean_brightness);
      if (history.size() > 90) {
        history.pop_front();
      }

      std::string ae_status = "STABLE";
      if (history.size() >= 30) {
        double min_val = *std::min_element(history.begin(), history.end());
        double max_val = *std::max_element(history.begin(), history.end());
        if ((max_val - min_val) > 25.0) {
          ae_status = "ADJUSTING (AE Active)";
        }
      }

      // Draw HUD overlays
      char b_str[64];
      snprintf(b_str, sizeof(b_str), "Mean Brightness: %.1f", mean_brightness);
      std::string status_str = "AE Status: " + ae_status;

      cv::putText(frame, b_str, cv::Point(20, 40),
                  cv::FONT_HERSHEY_SIMPLEX, 1.0, cv::Scalar(0, 255, 0), 2);
      cv::putText(frame, status_str, cv::Point(20, 80),
                  cv::FONT_HERSHEY_SIMPLEX, 0.7, 
                  ae_status == "STABLE" ? cv::Scalar(0, 200, 0) : cv::Scalar(0, 255, 255), 2);

      cv::imshow("SIYI A8 - C++ AE Analyzer", frame);
    }

    int key = cv::waitKey(33); // ~30Hz GUI rate limit
    if (key == 'q' || key == 27) {
      break;
    }
  }

  cv::destroyAllWindows();
  rclcpp::shutdown();
  spin_thread.join();
  return 0;
}
