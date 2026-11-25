from django.urls import path

from .views import team, workspace

urlpatterns = [
    path("", workspace.app_home, name="app_home"),
    path("new/", workspace.organization_create, name="organization_create"),
    path("<slug:org_slug>/", workspace.dashboard, name="dashboard"),
    path("<slug:org_slug>/settings/", workspace.organization_settings,
         name="organization_settings"),
    path("<slug:org_slug>/settings/danger/", workspace.organization_danger,
         name="organization_danger"),
    path("<slug:org_slug>/team/", team.team, name="team"),
    path("<slug:org_slug>/team/invite/", team.team_invite, name="team_invite"),
    path("<slug:org_slug>/team/leave/", team.leave, name="team_leave"),
    path("<slug:org_slug>/team/members/<int:member_id>/role/", team.member_role,
         name="team_member_role"),
    path("<slug:org_slug>/team/members/<int:member_id>/remove/", team.member_remove,
         name="team_member_remove"),
    path("<slug:org_slug>/team/invitations/<int:invitation_id>/revoke/",
         team.invitation_revoke, name="team_invitation_revoke"),
]
