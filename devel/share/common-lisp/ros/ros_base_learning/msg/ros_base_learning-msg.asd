
(cl:in-package :asdf)

(defsystem "ros_base_learning-msg"
  :depends-on (:roslisp-msg-protocol :roslisp-utils :actionlib_msgs-msg
               :std_msgs-msg
)
  :components ((:file "_package")
    (:file "CounterAction" :depends-on ("_package_CounterAction"))
    (:file "_package_CounterAction" :depends-on ("_package"))
    (:file "CounterActionFeedback" :depends-on ("_package_CounterActionFeedback"))
    (:file "_package_CounterActionFeedback" :depends-on ("_package"))
    (:file "CounterActionGoal" :depends-on ("_package_CounterActionGoal"))
    (:file "_package_CounterActionGoal" :depends-on ("_package"))
    (:file "CounterActionResult" :depends-on ("_package_CounterActionResult"))
    (:file "_package_CounterActionResult" :depends-on ("_package"))
    (:file "CounterFeedback" :depends-on ("_package_CounterFeedback"))
    (:file "_package_CounterFeedback" :depends-on ("_package"))
    (:file "CounterGoal" :depends-on ("_package_CounterGoal"))
    (:file "_package_CounterGoal" :depends-on ("_package"))
    (:file "CounterResult" :depends-on ("_package_CounterResult"))
    (:file "_package_CounterResult" :depends-on ("_package"))
  ))