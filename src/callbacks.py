from aiogram.filters.callback_data import CallbackData




CB_BACK = "back_to_main"


CB_ADD_CLASS = "add_class"
CB_ADD_STUDENT = "add_student"
CB_ENROLL = "enroll"
CB_REGISTER = "register"
CB_ADD_TASK = "add_task"
CB_LIST_TASKS = "list_tasks"
CB_GEN = "gen"
CB_SETTINGS = "settings"



CB_ENROLL_PICK_STU = "enroll_pick_stu:"
CB_ENROLL_PICK_CLS = "enroll_pick_cls:"
CB_STU_AFTER_ADD_SKIP = "stu_after_add_skip"
CB_STU_AFTER_ADD_ENROLL = "stu_after_add_enroll:"
CB_ADD_TASK_PICK_CLASS = "addtask_pick_cls:"













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

CB_LA_ASSIGN_PICK_CLS = "la_assign_pick_cls:"
class StudentCB(CallbackData, prefix="student"):
    action: str
    page: int | None = None

class TaskCB(CallbackData, prefix="task"):
    action: str
    task_id: int
    page: int | None = None

CB_STU_MENU  = "stu_menu"
CB_STU_TASKS = "stu_tasks"

CB_STU_MENU      = "stu_menu"
CB_STU_TASKS     = "stu_tasks"
CB_STU_TEACHERS  = "stu_teachers"
CB_STU_GROUPS    = "stu_groups"
CB_STU_SCHEDULE  = "stu_schedule"
CB_STU_INFO      = "stu_info"

class StudentCB(CallbackData, prefix="student"):
    action: str
    page: int | None = None

class TaskCB(CallbackData, prefix="task"):
    action: str
    task_id: int
    page: int | None = None

CB_STU_MENU  = "stu_menu"
CB_STU_TASKS = "stu_tasks"

CB_STU_MENU      = "stu_menu"
CB_STU_TASKS     = "stu_tasks"
CB_STU_TEACHERS  = "stu_teachers"
CB_STU_GROUPS    = "stu_groups"
CB_STU_SCHEDULE  = "stu_schedule"
CB_STU_INFO      = "stu_info"


CB_TEACHER_MENU = "teacher_menu"

CB_T_MAIN = "t_main"
CB_T_ASSIGN_STUDENT = "t_assign_student"
CB_T_EDIT_STUDENTS = "t_edit_students"
CB_T_CREATE_GROUP = "t_create_group"
CB_T_EDIT_GROUP = "t_edit_group"
CB_T_ADD_TASK = "t_add_task"
CB_T_LIST_TASKS = "t_list_tasks"
CB_T_ASSIGN_PICK_CLS = "t_assign_pick_cls:"


CB_T_EDIT_PICK_CLS = "t_edit_pick_cls:"


CB_T_EDIT_PICK_STU = "t_edit_pick_stu:"


CB_T_EDIT_ACTION = "t_edit_action:"



CB_T_EDIT_PICK_NEWCLS = "t_edit_pick_newcls:"


CB_T_EDIT_BACK_CLASSES  = "t_edit_back_classes"
CB_T_EDIT_BACK_STUDENTS = "t_edit_back_students:"
CB_T_EDIT_BACK_ACTIONS  = "t_edit_back_actions:"


CB_T_GEDIT_PICK_CLS       = "t_gedit_pick_cls:"
CB_T_GEDIT_ACTION         = "t_gedit_action:"
CB_T_GDEL_PICK_STU        = "t_gdel_pick_stu:"
CB_T_GEDIT_BACK_GROUPS    = "t_gedit_back_groups"
CB_T_GEDIT_BACK_ACTIONS   = "t_gedit_back_actions:"
CB_T_GEDIT_BACK_STUDENTS  = "t_gedit_back_students:"
CB_T_GADD_PICK_STU        = "t_gadd_pick_stu:"



CB_T_TASK_PICK_CLS     = "t_task_pick_cls:"
CB_T_TASK_SCOPE        = "t_task_scope:"
CB_T_TASK_PICK_STU     = "t_task_pick_stu:"
CB_T_TASK_PICK_DONE    = "t_task_pick_done:"

CB_T_TASK_BACK_CLASSES = "t_task_back_classes"
CB_T_TASK_BACK_SCOPE   = "t_task_back_scope:"
CB_T_TASK_BACK_STUS    = "t_task_back_stus:"



CB_T_VTASK_PICK_CLS      = "t_vtask_pick_cls:"
CB_T_VTASK_CLASS_MENU    = "t_vtask_class_menu:"
CB_T_VTASK_PICK_STU      = "t_vtask_pick_stu:"
CB_T_VTASK_OPEN          = "t_vtask_open:"
CB_T_VTASK_GROUP_TASKS   = "t_vtask_group_tasks:"
CB_T_VTASK_STUDENTS      = "t_vtask_students:"
CB_T_VTASK_EDIT_DEADLINE = "t_vtask_edit_deadline:"

CB_T_VTASK_BACK_CLASSES  = "t_vtask_back_classes"
CB_T_VTASK_BACK_STUDENTS = "t_vtask_back_students:"
CB_T_VTASK_BACK_TASKS    = "t_vtask_back_tasks:"
CB_T_VTASK_EDIT_TITLE    = "t_vtask_edit_title:"
CB_T_VTASK_EDIT_DESC     = "t_vtask_edit_desc:"
CB_T_VTASK_DELETE        = "t_vtask_delete:"

