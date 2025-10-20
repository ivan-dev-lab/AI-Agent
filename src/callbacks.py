from aiogram.filters.callback_data import CallbackData

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

# ===== Меню Глобального администратора =====
CB_GA_MENU = "ga_menu"

# Разделы панели
CB_GA_SEC_CORE = "ga_sec_core"      # Основные
CB_GA_SEC_MORE = "ga_sec_more"      # Дополнительные
CB_GA_SEC_INFO = "ga_sec_info"      # Информационные
CB_GA_BACK_TO_CORE = "ga_back_to_core"
# Действия (основные)
CB_GA_ADD_SCHOOL    = "ga_add_school"     # Добавить учебное заведение
CB_GA_EDIT_SCHOOLS  = "ga_edit_schools"   # Редактирование учебных заведений
CB_GA_ASSIGN_LA     = "ga_assign_la"      # Назначить локального администратора
CB_GA_EDIT_LA       = "ga_edit_la"        # Редактирование ЛА

# Действия (дополнительные)
CB_GA_ASSIGN_TEACHER  = "ga_assign_teacher"   # Назначить учителя
CB_GA_ASSIGN_STUDENT  = "ga_assign_student"   # Назначить ученика
CB_GA_EDIT_TEACHERS   = "ga_edit_teachers"    # Редактирование учителей
CB_GA_EDIT_STUDENTS   = "ga_edit_students"    # Редактирование учеников

# Действия (информационные)
CB_GA_LIST_SCHOOLS   = "ga_list_schools"    # Просмотреть список УЗ
CB_GA_LIST_LA        = "ga_list_la"         # Просмотреть список ЛА
CB_GA_LIST_TEACHERS  = "ga_list_teachers"   # Просмотреть список учителей
CB_GA_LIST_STUDENTS  = "ga_list_students"   # Просмотреть список учеников
CB_GA_LIST_GA        = "ga_list_ga"         # Просмотреть список ГА

# ===== Префиксы для редактирования конкретного УЗ =====
CB_GA_ED_S_PICK  = "ga_es_pick:"   # +<school_id>
CB_GA_ED_S_NAME  = "ga_es_name:"   # +<school_id>
CB_GA_ED_S_SHORT = "ga_es_short:"  # +<school_id>
CB_GA_ED_S_ADDR  = "ga_es_addr:"   # +<school_id>
CB_GA_ED_S_TZ    = "ga_es_tz:"     # +<school_id>

class StudentCB(CallbackData, prefix="student"):
    action: str              # "menu" | "tasks"
    page: int | None = None  # страница списка (пагинация)

class TaskCB(CallbackData, prefix="task"):
    action: str              # "detail"
    task_id: int             # ID задания
    page: int | None = None  # из какой страницы списка вернуться

CB_STU_MENU  = "stu_menu"
CB_STU_TASKS = "stu_tasks"  # открыть список заданий ученика

CB_STU_MENU      = "stu_menu"
CB_STU_TASKS     = "stu_tasks"
CB_STU_TEACHERS  = "stu_teachers"
CB_STU_GROUPS    = "stu_groups"
CB_STU_SCHEDULE  = "stu_schedule"
CB_STU_INFO      = "stu_info"
