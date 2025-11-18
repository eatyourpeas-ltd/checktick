from django.urls import path

from . import views, views_data_governance as gov_views

app_name = "surveys"

urlpatterns = [
    path("", views.survey_list, name="list"),
    # User management hub (must be before slug routes)
    path("manage/users/", views.user_management_hub, name="user_management_hub"),
    # Dataset management routes (must be before slug routes)
    path("datasets/", views.dataset_list, name="dataset_list"),
    path("datasets/create/", views.dataset_create, name="dataset_create"),
    path("datasets/<int:dataset_id>/", views.dataset_detail, name="dataset_detail"),
    path("datasets/<int:dataset_id>/edit/", views.dataset_edit, name="dataset_edit"),
    path(
        "datasets/<int:dataset_id>/delete/",
        views.dataset_delete,
        name="dataset_delete",
    ),
    path("<slug:slug>/bulk-upload/", views.bulk_upload, name="bulk_upload"),
    path("create/", views.survey_create, name="create"),
    # Repeats (collections) integrated with groups
    path(
        "<slug:slug>/groups/repeat/create",
        views.survey_groups_repeat_create,
        name="survey_groups_repeat_create",
    ),
    path(
        "<slug:slug>/groups/<int:gid>/repeat/remove",
        views.survey_group_repeat_remove,
        name="survey_group_repeat_remove",
    ),
    path(
        "<slug:slug>/groups/template/create",
        views.survey_group_create_from_template,
        name="groups_create_from_template",
    ),
    path("<slug:slug>/preview/", views.survey_preview, name="preview"),
    path(
        "<slug:slug>/preview/thank-you/",
        views.survey_preview_thank_you,
        name="preview_thank_you",
    ),
    # Participant routes
    path("<slug:slug>/take/", views.survey_take, name="take"),
    path(
        "<slug:slug>/take/unlisted/<str:key>/",
        views.survey_take_unlisted,
        name="take_unlisted",
    ),
    path(
        "<slug:slug>/take/token/<str:token>/",
        views.survey_take_token,
        name="take_token",
    ),
    path("<slug:slug>/thank-you/", views.survey_thank_you, name="thank_you"),
    path("<slug:slug>/closed/", views.survey_closed, name="closed"),
    path("<slug:slug>/", views.survey_detail, name="detail"),
    path("<slug:slug>/dashboard/", views.survey_dashboard, name="dashboard"),
    path("<slug:slug>/delete/", views.survey_delete, name="delete"),
    path(
        "<slug:slug>/publish/",
        views.survey_publish_settings,
        name="publish_settings",
    ),
    path(
        "<slug:slug>/dashboard/publish",
        views.survey_publish_update,
        name="publish_update",
    ),
    path(
        "<slug:slug>/encryption/setup",
        views.survey_encryption_setup,
        name="encryption_setup",
    ),
    path(
        "<slug:slug>/encryption/display",
        views.survey_encryption_display,
        name="encryption_display",
    ),
    path("<slug:slug>/tokens/", views.survey_tokens, name="tokens"),
    path(
        "<slug:slug>/invites/pending/",
        views.survey_invites_pending,
        name="invites_pending",
    ),
    path(
        "<slug:slug>/invites/<int:token_id>/resend/",
        views.survey_invite_resend,
        name="invite_resend",
    ),
    path(
        "<slug:slug>/tokens/export.csv",
        views.survey_tokens_export_csv,
        name="tokens_export_csv",
    ),
    path("<slug:slug>/style/update", views.survey_style_update, name="style_update"),
    path("<slug:slug>/groups/", views.survey_groups, name="groups"),
    path(
        "<slug:slug>/groups/reorder",
        views.survey_groups_reorder,
        name="survey_groups_reorder",
    ),
    path(
        "<slug:slug>/groups/create",
        views.survey_group_create,
        name="survey_group_create",
    ),
    path(
        "<slug:slug>/groups/<int:gid>/edit",
        views.survey_group_edit,
        name="survey_group_edit",
    ),
    path(
        "<slug:slug>/groups/<int:gid>/delete",
        views.survey_group_delete,
        name="survey_group_delete",
    ),
    path("<slug:slug>/unlock/", views.survey_unlock, name="unlock"),
    path(
        "<slug:slug>/organization-recovery/",
        views.organization_key_recovery,
        name="organization_key_recovery",
    ),
    path("<slug:slug>/export.csv", views.survey_export_csv, name="export_csv"),
    # Group question management (per-group)
    path(
        "<slug:slug>/builder/groups/<int:gid>/",
        views.group_builder,
        name="group_builder",
    ),
    path(
        "<slug:slug>/builder/questions/create",
        views.builder_question_create,
        name="builder_question_create",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/create",
        views.builder_group_question_create,
        name="builder_group_question_create",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/templates/add",
        views.builder_group_template_add,
        name="builder_group_template_add",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/template/patient",
        views.builder_question_template_patient_update,
        name="builder_question_template_patient_update",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/<int:qid>/template/patient",
        views.builder_group_question_template_patient_update,
        name="builder_group_question_template_patient_update",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/template/professional",
        views.builder_question_template_professional_update,
        name="builder_question_template_professional_update",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/<int:qid>/template/professional",
        views.builder_group_question_template_professional_update,
        name="builder_group_question_template_professional_update",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/edit",
        views.builder_question_edit,
        name="builder_question_edit",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/copy",
        views.builder_question_copy,
        name="builder_question_copy",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/conditions/create",
        views.builder_question_condition_create,
        name="builder_question_condition_create",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/conditions/<int:cid>/update",
        views.builder_question_condition_update,
        name="builder_question_condition_update",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/conditions/<int:cid>/delete",
        views.builder_question_condition_delete,
        name="builder_question_condition_delete",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/<int:qid>/edit",
        views.builder_group_question_edit,
        name="builder_group_question_edit",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/<int:qid>/copy",
        views.builder_group_question_copy,
        name="builder_group_question_copy",
    ),
    path(
        "<slug:slug>/builder/questions/<int:qid>/delete",
        views.builder_question_delete,
        name="builder_question_delete",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/<int:qid>/delete",
        views.builder_group_question_delete,
        name="builder_group_question_delete",
    ),
    path(
        "<slug:slug>/builder/questions/reorder",
        views.builder_questions_reorder,
        name="builder_questions_reorder",
    ),
    path(
        "<slug:slug>/builder/groups/<int:gid>/questions/reorder",
        views.builder_group_questions_reorder,
        name="builder_group_questions_reorder",
    ),
    path(
        "<slug:slug>/builder/groups/create",
        views.builder_group_create,
        name="builder_group_create",
    ),
    path(
        "<slug:slug>/builder/demographics/update",
        views.builder_demographics_update,
        name="builder_demographics_update",
    ),
    path(
        "<slug:slug>/builder/professional/update",
        views.builder_professional_update,
        name="builder_professional_update",
    ),
    # User management portal
    path("org/<int:org_id>/users/", views.org_users, name="org_users"),
    path("<slug:slug>/users/", views.survey_users, name="survey_users"),
    # Data Governance (exports, retention, legal holds, custodians)
    path(
        "<slug:slug>/export/",
        gov_views.survey_export_create,
        name="survey_export_create",
    ),
    path(
        "<slug:slug>/export/<uuid:export_id>/",
        gov_views.survey_export_download,
        name="survey_export_download",
    ),
    path(
        "<slug:slug>/export/<uuid:export_id>/download/<str:token>/",
        gov_views.survey_export_file,
        name="survey_export_file",
    ),
    path(
        "<slug:slug>/retention/extend/",
        gov_views.survey_extend_retention,
        name="survey_extend_retention",
    ),
    path(
        "<slug:slug>/legal-hold/place/",
        gov_views.survey_legal_hold_place,
        name="survey_legal_hold_place",
    ),
    path(
        "<slug:slug>/legal-hold/remove/",
        gov_views.survey_legal_hold_remove,
        name="survey_legal_hold_remove",
    ),
    path(
        "<slug:slug>/custodian/grant/",
        gov_views.survey_custodian_grant,
        name="survey_custodian_grant",
    ),
    path(
        "<slug:slug>/custodian/<int:custodian_id>/revoke/",
        gov_views.survey_custodian_revoke,
        name="survey_custodian_revoke",
    ),
    # Published question group templates
    path(
        "templates/",
        views.published_templates_list,
        name="published_templates_list",
    ),
    path(
        "templates/<int:template_id>/",
        views.published_template_detail,
        name="published_template_detail",
    ),
    path(
        "templates/<int:template_id>/preview/",
        views.published_template_preview,
        name="published_template_preview",
    ),
    path(
        "<slug:slug>/groups/<int:gid>/publish/",
        views.question_group_publish,
        name="question_group_publish",
    ),
    path(
        "templates/<int:template_id>/import/<slug:survey_slug>/",
        views.published_template_import,
        name="published_template_import",
    ),
    path(
        "templates/<int:template_id>/delete/",
        views.published_template_delete,
        name="published_template_delete",
    ),
]
