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
CB_T_ASSIGN_PICK_CLS = "t_assign_pick_cls:"


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

# --- добавляем для роли teacher ---
CB_TEACHER_MENU = "teacher_menu"

CB_T_MAIN = "t_main"            # показать основное меню учителя
CB_T_ASSIGN_STUDENT = "t_assign_student"   # назначить ученика
CB_T_EDIT_STUDENTS = "t_edit_students"     # редактировать учеников
CB_T_CREATE_GROUP = "t_create_group"       # создать группу
CB_T_EDIT_GROUP = "t_edit_group"           # редактировать группу (добав/удал)
CB_T_ADD_TASK = "t_add_task"               # добавить задание
CB_T_LIST_TASKS = "t_list_tasks"           # список заданий
CB_T_ASSIGN_PICK_CLS = "t_assign_pick_cls:"   # +<class_id>

# Выбор класса для редактирования
CB_T_EDIT_PICK_CLS = "t_edit_pick_cls:"          # +<class_id>

# Выбор ученика внутри класса
CB_T_EDIT_PICK_STU = "t_edit_pick_stu:"          # +<student_id>:<class_id>

# Действие над учеником
CB_T_EDIT_ACTION = "t_edit_action:"               # +<action>:<student_id>:<class_id>
# action ∈ {"fio", "group"}

# Выбор новой группы (для переноса ученика)
CB_T_EDIT_PICK_NEWCLS = "t_edit_pick_newcls:"     # +<new_class_id>:<student_id>:<old_class_id>

# «Назад» внутри мастера
CB_T_EDIT_BACK_CLASSES  = "t_edit_back_classes"   # назад к списку классов
CB_T_EDIT_BACK_STUDENTS = "t_edit_back_students:" # +<class_id> — назад к списку учеников
CB_T_EDIT_BACK_ACTIONS  = "t_edit_back_actions:"  # +<student_id>:<class_id> — назад к действиям

# --- редактирование группы (group edit) ---
CB_T_GEDIT_PICK_CLS       = "t_gedit_pick_cls:"
CB_T_GEDIT_ACTION         = "t_gedit_action:"
CB_T_GDEL_PICK_STU        = "t_gdel_pick_stu:"
CB_T_GEDIT_BACK_GROUPS    = "t_gedit_back_groups"
CB_T_GEDIT_BACK_ACTIONS   = "t_gedit_back_actions:"
CB_T_GEDIT_BACK_STUDENTS  = "t_gedit_back_students:"
CB_T_GADD_PICK_STU        = "t_gadd_pick_stu:"   # +<student_id>:<class_id>


# --- мастер добавления задания ---
CB_T_TASK_PICK_CLS     = "t_task_pick_cls:"          # +<class_id>
CB_T_TASK_SCOPE        = "t_task_scope:"             # +<scope>:<class_id> ; scope ∈ {"cls","sel"}
CB_T_TASK_PICK_STU     = "t_task_pick_stu:"          # +<student_id>:<class_id> (переключатель)
CB_T_TASK_PICK_DONE    = "t_task_pick_done:"         # +<class_id> (завершить выбор учеников)

CB_T_TASK_BACK_CLASSES = "t_task_back_classes"       # назад к списку групп
CB_T_TASK_BACK_SCOPE   = "t_task_back_scope:"        # +<class_id> — назад к выбору охвата
CB_T_TASK_BACK_STUS    = "t_task_back_stus:"         # +<class_id> — назад к списку учеников


# --- Просмотр заданий учителем ---
CB_T_VTASK_PICK_CLS      = "t_vtask_pick_cls:"       # +<class_id>
CB_T_VTASK_PICK_STU      = "t_vtask_pick_stu:"       # +<student_id>:<class_id>
CB_T_VTASK_OPEN          = "t_vtask_open:"           # +<task_id>:<student_id>:<class_id>

CB_T_VTASK_BACK_CLASSES  = "t_vtask_back_classes"    # назад к списку групп
CB_T_VTASK_BACK_STUDENTS = "t_vtask_back_students:"  # +<class_id> — назад к ученикам
CB_T_VTASK_BACK_TASKS    = "t_vtask_back_tasks:"     # +<student_id>:<class_id> — назад к списку задач ученика
