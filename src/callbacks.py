# src/callbacks.py
# Общие
CB_BACK = "back_to_main"

# Старые/имеющиеся (оставляем как есть)
CB_ADD_CLASS = "add_class"
CB_ADD_STUDENT = "add_student"
CB_ENROLL = "enroll"
CB_REGISTER = "register"
CB_ADD_TASK = "add_task"
CB_LIST_TASKS = "list_tasks"
CB_GEN = "gen"
CB_SETTINGS = "settings"

# Ветки выбора (оставляем, если используются)
CB_ENROLL_PICK_STU = "enroll_pick_stu:"       # +<student_id>
CB_ENROLL_PICK_CLS = "enroll_pick_cls:"       # +<student_id>:<class_id>
CB_STU_AFTER_ADD_SKIP = "stu_after_add_skip"
CB_STU_AFTER_ADD_ENROLL = "stu_after_add_enroll:"  # +<student_id>
CB_ADD_TASK_PICK_CLASS = "addtask_pick_cls:"  # +<class_id>

# ===== Новые коллбэки: меню Глобального администратора =====
CB_GA_MENU = "ga_menu"

# --- Глобальный админ: разделы панели ---
CB_GA_SEC_CORE = "ga_sec_core"      # Основные
CB_GA_SEC_MORE = "ga_sec_more"      # Дополнительные
CB_GA_SEC_INFO = "ga_sec_info"      # Информационные

# --- Глобальный админ: действия (основные) ---
CB_GA_ADD_SCHOOL    = "ga_add_school"
CB_GA_EDIT_SCHOOLS  = "ga_edit_schools"
CB_GA_ASSIGN_LA     = "ga_assign_la"
CB_GA_EDIT_LA       = "ga_edit_la"

# --- Глобальный админ: действия (дополнительные) ---
CB_GA_ASSIGN_TEACHER  = "ga_assign_teacher"
CB_GA_ASSIGN_STUDENT  = "ga_assign_student"
CB_GA_EDIT_TEACHERS   = "ga_edit_teachers"
CB_GA_EDIT_STUDENTS   = "ga_edit_students"

# --- Глобальный админ: действия (информационные) ---
CB_GA_LIST_SCHOOLS   = "ga_list_schools"
CB_GA_LIST_LA        = "ga_list_la"
CB_GA_LIST_TEACHERS  = "ga_list_teachers"
CB_GA_LIST_STUDENTS  = "ga_list_students"
CB_GA_LIST_GA        = "ga_list_ga"
