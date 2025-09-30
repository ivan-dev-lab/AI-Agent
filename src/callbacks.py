# -*- coding: utf-8 -*-

# simple callbacks
CB_MAIN = "main"
CB_ADD_CLASS = "add_class"
CB_ADD_STUDENT = "add_student"
CB_ENROLL = "enroll"
CB_REGISTER = "register"
CB_ADD_TASK = "add_task"
CB_LIST_TASKS = "list_tasks"
CB_GEN = "gen"
CB_SETTINGS = "settings"
CB_BACK = "back_to_main"

# prefixed callbacks
CB_ENROLL_PICK_STU = "enroll_pick_stu:"       # +<student_id>
CB_ENROLL_PICK_CLS = "enroll_pick_cls:"       # +<student_id>:<class_id>

# after student added
CB_STU_AFTER_ADD_ENROLL = "stu_after_add_enroll:"  # +<student_id>
CB_STU_AFTER_ADD_SKIP = "stu_after_add_skip"

# add task: pick class
CB_ADD_TASK_PICK_CLASS = "addtask_pick_cls:"  # +<class_id>
