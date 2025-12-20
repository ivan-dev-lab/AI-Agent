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

# Разделы панели
# Действия (основные)

# Действия (дополнительные)

# Действия (информационные)

# ===== Префиксы для редактирования конкретного УЗ =====

# Local admin callbacks (LA)
CB_LA_MENU = "la_menu"
CB_LA_SEC_CORE = "la_sec_core"
CB_LA_SEC_INFO = "la_sec_info"
CB_LA_ASSIGN_TEACHER = "la_assign_teacher"
CB_LA_ASSIGN_STUDENT = "la_assign_student"
CB_LA_EDIT_TEACHERS = "la_edit_teachers"
CB_LA_EDIT_STUDENTS = "la_edit_students"
CB_LA_LIST_TEACHERS = "la_list_teachers"
CB_LA_LIST_STUDENTS = "la_list_students"
CB_LA_LIST_LOCAL_ADMINS = "la_list_local_admins"
CB_LA_CREATE_SCHOOL = "la_create_school"
CB_LA_BACK_TO_CORE = "la_back_to_core"

CB_LA_ASSIGN_PICK_CLS = "la_assign_pick_cls:"   # +<class_id> при выборе класса
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
CB_T_VTASK_CLASS_MENU    = "t_vtask_class_menu:"     # +<class_id>
CB_T_VTASK_PICK_STU      = "t_vtask_pick_stu:"       # +<student_id>:<class_id>
CB_T_VTASK_OPEN          = "t_vtask_open:"           # +<task_id>:<student_id>:<class_id>
CB_T_VTASK_GROUP_TASKS   = "t_vtask_group_tasks:"    # +<class_id>
CB_T_VTASK_STUDENTS      = "t_vtask_students:"       # +<class_id>
CB_T_VTASK_EDIT_DEADLINE = "t_vtask_edit_deadline:"  # +<task_id>:<student_id>:<class_id>

CB_T_VTASK_BACK_CLASSES  = "t_vtask_back_classes"    # назад к списку групп
CB_T_VTASK_BACK_STUDENTS = "t_vtask_back_students:"  # +<class_id> — назад к ученикам
CB_T_VTASK_BACK_TASKS    = "t_vtask_back_tasks:"     # +<student_id>:<class_id> — назад к списку задач ученика
CB_T_VTASK_EDIT_TITLE    = "t_vtask_edit_title:"     # +<task_id>:<student_id>:<class_id>
CB_T_VTASK_EDIT_DESC     = "t_vtask_edit_desc:"      # +<task_id>:<student_id>:<class_id>
CB_T_VTASK_DELETE        = "t_vtask_delete:"         # +<task_id>:<student_id>:<class_id>

