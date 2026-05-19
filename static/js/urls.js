'use strict';

const API_BASE = '/api/v1/';

export const API_URLS = {
    delivery_teams: {
        list: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/`,
        },
        stats: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/stats/`,
        },
        create: {
            method: 'POST',
            href: `${API_BASE}delivery-teams/`,
        },
        detail: (teamId) => ({
            method: 'GET',
            href: `${API_BASE}delivery-teams/${teamId}/`,
        }),
        update: (teamId) => ({
            method: 'PATCH',
            href: `${API_BASE}delivery-teams/${teamId}/`,
        }),
        delete: (teamId) => ({
            method: 'DELETE',
            href: `${API_BASE}delivery-teams/${teamId}/`,
        }),
        members: (teamId) => ({
            method: 'GET',
            href: `${API_BASE}delivery-teams/${teamId}/members/`,
        }),
        assign_member: (teamId) => ({
            method: 'POST',
            href: `${API_BASE}delivery-teams/${teamId}/assign-member/`,
        }),
        unassign_member: (teamId, memberId) => ({
            method: 'DELETE',
            href: `${API_BASE}delivery-teams/${teamId}/unassign-member/${memberId}/`,
        }),
        leaves: (teamId) => ({
            method: 'GET',
            href: `${API_BASE}delivery-teams/${teamId}/leaves/`,
        }),
        projects: (teamId) => ({
            method: 'GET',
            href: `${API_BASE}delivery-teams/${teamId}/projects/`,
        }),
        options: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/options/`,
        },
        import_spec: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/import/specifications/`,
        },
        import_sample: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/import/sample/`,
        },
        import: {
            method: 'POST',
            href: `${API_BASE}delivery-teams/import/`,
        },
        export: {
            method: 'GET',
            href: `${API_BASE}delivery-teams/export/`,
        },
    },
    skills: {
        list: { method: 'GET', href: `${API_BASE}skills/` },
        stats: { method: 'GET', href: `${API_BASE}skills/stats/` },
        new: { method: 'POST', href: `${API_BASE}skills/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}skills/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}skills/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}skills/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}skills/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}skills/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}skills/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}skills/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}skills/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}skills/import/` },
        export: { method: 'GET', href: `${API_BASE}skills/export/` },
    },
    locations: {
        list: { method: 'GET', href: `${API_BASE}locations/` },
        stats: { method: 'GET', href: `${API_BASE}locations/stats/` },
        new: { method: 'POST', href: `${API_BASE}locations/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}locations/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}locations/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}locations/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}locations/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}locations/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}locations/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}locations/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}locations/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}locations/import/` },
        export: { method: 'GET', href: `${API_BASE}locations/export/` },
    },
    roles: {
        list: { method: 'GET', href: `${API_BASE}roles/` },
        stats: { method: 'GET', href: `${API_BASE}roles/stats/` },
        new: { method: 'POST', href: `${API_BASE}roles/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}roles/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}roles/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}roles/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}roles/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}roles/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}roles/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}roles/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}roles/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}roles/import/` },
        export: { method: 'GET', href: `${API_BASE}roles/export/` },
    },
    employment_types: {
        list: { method: 'GET', href: `${API_BASE}employment-types/` },
        stats: { method: 'GET', href: `${API_BASE}employment-types/stats/` },
        new: { method: 'POST', href: `${API_BASE}employment-types/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}employment-types/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}employment-types/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}employment-types/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}employment-types/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}employment-types/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}employment-types/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}employment-types/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}employment-types/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}employment-types/import/` },
        export: { method: 'GET', href: `${API_BASE}employment-types/export/` },
    },
    team_members: {
        list: { method: 'GET', href: `${API_BASE}team-members/` },
        stats: { method: 'GET', href: `${API_BASE}team-members/stats/` },
        new: { method: 'POST', href: `${API_BASE}team-members/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}team-members/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}team-members/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}team-members/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}team-members/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}team-members/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}team-members/options/` },
        move_team: (pk) => ({ method: 'POST', href: `${API_BASE}team-members/${pk}/move-team/` }),
        assign_team: (pk) => ({ method: 'POST', href: `${API_BASE}team-members/${pk}/assign-team/` }),
        unassign_team: (pk, teamId) => ({ method: 'DELETE', href: `${API_BASE}team-members/${pk}/unassign-team/${teamId}/` }),
        history: (pk) => ({ method: 'GET', href: `${API_BASE}team-members/${pk}/history/` }),
        leaves: (pk) => ({ method: 'GET', href: `${API_BASE}team-members/${pk}/leaves/` }),
        import_spec: { method: 'GET', href: `${API_BASE}team-members/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}team-members/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}team-members/import/` },
        export: { method: 'GET', href: `${API_BASE}team-members/export/` },
    },
    holidays: {
        list: { method: 'GET', href: `${API_BASE}holidays/` },
        stats: { method: 'GET', href: `${API_BASE}holidays/stats/` },
        new: { method: 'POST', href: `${API_BASE}holidays/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}holidays/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}holidays/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}holidays/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}holidays/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}holidays/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}holidays/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}holidays/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}holidays/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}holidays/import/` },
        export: { method: 'GET', href: `${API_BASE}holidays/export/` },
    },
    leaves: {
        list: { method: 'GET', href: `${API_BASE}leaves/` },
        stats: { method: 'GET', href: `${API_BASE}leaves/stats/` },
        new: { method: 'POST', href: `${API_BASE}leaves/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}leaves/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}leaves/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}leaves/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}leaves/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}leaves/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}leaves/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}leaves/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}leaves/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}leaves/import/` },
        export: { method: 'GET', href: `${API_BASE}leaves/export/` },
    },
    financial_years: {
        list: { method: 'GET', href: `${API_BASE}fy/` },
        stats: { method: 'GET', href: `${API_BASE}fy/stats/` },
        new: { method: 'POST', href: `${API_BASE}fy/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}fy/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}fy/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}fy/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}fy/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}fy/${pk}/` }),
        active: { method: 'GET', href: `${API_BASE}fy/active/` },
        set_active: (pk) => ({ method: 'POST', href: `${API_BASE}fy/${pk}/set-active/` }),
        summary: { method: 'GET', href: `${API_BASE}fy/summary/` },
        options: { method: 'GET', href: `${API_BASE}fy/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}fy/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}fy/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}fy/import/` },
        export: { method: 'GET', href: `${API_BASE}fy/export/` },
    },
    sprints: {
        list: { method: 'GET', href: `${API_BASE}sprints/` },
        stats: { method: 'GET', href: `${API_BASE}sprints/stats/` },
        new: { method: 'POST', href: `${API_BASE}sprints/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}sprints/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}sprints/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}sprints/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}sprints/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}sprints/${pk}/` }),
        active: { method: 'GET', href: `${API_BASE}sprints/active/` },
        set_active: (pk) => ({ method: 'POST', href: `${API_BASE}sprints/${pk}/set-active/` }),
        summary: { method: 'GET', href: `${API_BASE}sprints/summary/` },
        options: { method: 'GET', href: `${API_BASE}sprints/options/` },
        export: { method: 'GET', href: `${API_BASE}sprints/export/` },
        run_engine: { method: 'POST', href: `${API_BASE}sprints/run-engine/` },
        capacity: (pk) => ({ method: 'GET', href: `${API_BASE}sprints/${pk}/capacity/` }),
        close_sprint: (pk) => ({ method: 'POST', href: `${API_BASE}sprints/${pk}/close-sprint/` }),
        unlock_sprint: (pk) => ({ method: 'POST', href: `${API_BASE}sprints/${pk}/unlock-sprint/` }),
    },
    sprint_capacity: {
        list: { method: 'GET', href: `${API_BASE}sprint-capacity/` },
        rebuild: { method: 'POST', href: `${API_BASE}sprint-capacity/rebuild/` },
    },
    project_types: {
        list: { method: 'GET', href: `${API_BASE}project-types/` },
        stats: { method: 'GET', href: `${API_BASE}project-types/stats/` },
        new: { method: 'POST', href: `${API_BASE}project-types/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}project-types/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}project-types/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}project-types/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}project-types/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}project-types/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}project-types/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}project-types/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}project-types/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}project-types/import/` },
        export: { method: 'GET', href: `${API_BASE}project-types/export/` },
    },
    project_sub_statuses: {
        list: { method: 'GET', href: `${API_BASE}project-sub-statuses/` },
        new: { method: 'POST', href: `${API_BASE}project-sub-statuses/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}project-sub-statuses/${pk}/` }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}project-sub-statuses/${pk}/` }),
        edit: (pk) => ({ method: 'PUT', href: `${API_BASE}project-sub-statuses/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}project-sub-statuses/${pk}/` }),
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}project-sub-statuses/${pk}/` }),
        options: { method: 'GET', href: `${API_BASE}project-sub-statuses/options/` },
        import_spec: {
            method: 'GET',
            href: `${API_BASE}project-sub-statuses/import/specifications/`,
        },
        import_sample: { method: 'GET', href: `${API_BASE}project-sub-statuses/import/sample/` },
        import: { method: 'POST', href: `${API_BASE}project-sub-statuses/import/` },
        export: { method: 'GET', href: `${API_BASE}project-sub-statuses/export/` },
        reorder: (pk) => ({
            method: 'POST',
            href: `${API_BASE}project-sub-statuses/${pk}/reorder/`,
        }),
    },
    programmes: {
        list: {
            method: 'GET',
            href: `${API_BASE}programmes/`,
        },
        create: {
            method: 'POST',
            href: `${API_BASE}programmes/`,
        },
        detail: (programmeId) => ({
            method: 'GET',
            href: `${API_BASE}programmes/${programmeId}/`,
        }),
        update: (programmeId) => ({
            method: 'PATCH',
            href: `${API_BASE}programmes/${programmeId}/`,
        }),
        delete: (programmeId) => ({
            method: 'DELETE',
            href: `${API_BASE}programmes/${programmeId}/`,
        }),
        stats: {
            method: 'GET',
            href: `${API_BASE}programmes/stats/`,
        },
        options: {
            method: 'GET',
            href: `${API_BASE}programmes/options/`,
        },
        import_spec: {
            method: 'GET',
            href: `${API_BASE}programmes/import/specifications/`,
        },
        import_sample: {
            method: 'GET',
            href: `${API_BASE}programmes/import/sample/`,
        },
        import: {
            method: 'POST',
            href: `${API_BASE}programmes/import/`,
        },
        export: {
            method: 'GET',
            href: `${API_BASE}programmes/export/`,
        },
        summary: (programmeId) => ({
            method: 'GET',
            href: `${API_BASE}programmes/${programmeId}/summary/`,
        }),
    },
    contacts: {
        list: {
            method: 'GET',
            href: `${API_BASE}contacts/`,
        },
        new: {
            method: 'POST',
            href: `${API_BASE}contacts/`,
        },
        get: (contactId) => ({
            method: 'GET',
            href: `${API_BASE}contacts/${contactId}/`,
        }),
        detail: (contactId) => ({
            method: 'GET',
            href: `${API_BASE}contacts/${contactId}/`,
        }),
        edit: (contactId) => ({
            method: 'PUT',
            href: `${API_BASE}contacts/${contactId}/`,
        }),
        partial_edit: (contactId) => ({
            method: 'PATCH',
            href: `${API_BASE}contacts/${contactId}/`,
        }),
        delete: (contactId) => ({
            method: 'DELETE',
            href: `${API_BASE}contacts/${contactId}/`,
        }),
        stats: {
            method: 'GET',
            href: `${API_BASE}contacts/stats/`,
        },
        options: {
            method: 'GET',
            href: `${API_BASE}contacts/options/`,
        },
        import_spec: {
            method: 'GET',
            href: `${API_BASE}contacts/import/specifications/`,
        },
        import_sample: {
            method: 'GET',
            href: `${API_BASE}contacts/import/sample/`,
        },
        import: {
            method: 'POST',
            href: `${API_BASE}contacts/import/`,
        },
        export: {
            method: 'GET',
            href: `${API_BASE}contacts/export/`,
        },
        suggest: {
            method: 'GET',
            href: `${API_BASE}contacts/suggest/`,
        },
    },
    projects: {
        list: { method: 'GET', href: `${API_BASE}projects/` },
        new: { method: 'POST', href: `${API_BASE}projects/` },
        get: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/`,
        }),
        detail: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/`,
        }),
        get_operational: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/operational/`,
        }),
        get_teams: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/teams/`,
        }),
        list_labels: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/labels/`,
        }),
        suggest_label: (projectId) => ({
            method: 'GET',
            href: `${API_BASE}projects/${projectId}/labels/suggest/`,
        }),
        create_label: (projectId) => ({
            method: 'POST',
            href: `${API_BASE}projects/${projectId}/labels/`,
        }),
        edit_label: (projectId, labelId) => ({
            method: 'PATCH',
            href: `${API_BASE}projects/${projectId}/labels/${labelId}/`,
        }),
        delete_label: (projectId, labelId) => ({
            method: 'DELETE',
            href: `${API_BASE}projects/${projectId}/labels/${labelId}/`,
        }),
        edit: (projectId) => ({
            method: 'PUT',
            href: `${API_BASE}projects/${projectId}/`,
        }),
        partial_edit: (projectId) => ({
            method: 'PATCH',
            href: `${API_BASE}projects/${projectId}/`,
        }),
        edit_operational: (projectId) => ({
            method: 'PATCH',
            href: `${API_BASE}projects/${projectId}/teams/`,
        }),
        edit_teams: (projectId) => ({
            method: 'PATCH',
            href: `${API_BASE}projects/${projectId}/teams/`,
        }),
        delete: (projectId) => ({
            method: 'DELETE',
            href: `${API_BASE}projects/${projectId}/`,
        }),
        stats: {
            method: 'GET',
            href: `${API_BASE}projects/stats/`,
        },
        options: {
            method: 'GET',
            href: `${API_BASE}projects/options/`,
        },
        import_spec: {
            method: 'GET',
            href: `${API_BASE}projects/import/specifications/`,
        },
        import_sample: {
            method: 'GET',
            href: `${API_BASE}projects/import/sample/`,
        },
        import: {
            method: 'POST',
            href: `${API_BASE}projects/import/`,
        },
        export: {
            method: 'GET',
            href: `${API_BASE}projects/export/`,
        },
        status: {
            history: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/status/history/`,
            }),
        },
        tags: {
            get: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/tags/`,
            }),
            create: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/tags/`,
            }),
            delete: (projectId, tagId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/tags/${tagId}/`,
            }),
        },
        comments: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/comments/`,
            }),
            create: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/comments/`,
            }),
            patch: (projectId, commentId) => ({
                method: 'PATCH',
                href: `${API_BASE}projects/${projectId}/comments/${commentId}/`,
            }),
            delete: (projectId, commentId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/comments/${commentId}/`,
            }),
        },
        codes: {
            active: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/codes/`,
            }),
            create: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/codes/`,
            }),
            history: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/codes/history/`,
            }),
        },
        estimates: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/estimates/`,
            }),
            create: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/estimates/`,
            }),
            detail: (projectId, estimateId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/estimates/${estimateId}/`,
            }),
            edit: (projectId, estimateId) => ({
                method: 'PATCH',
                href: `${API_BASE}projects/${projectId}/estimates/${estimateId}/`,
            }),
            delete: (projectId, estimateId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/estimates/${estimateId}/`,
            }),
            options: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/estimates/options/`,
            }),
            history: (projectId, estimateId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/estimates/${estimateId}/history/`,
            }),
            sendApprovalEmail: (projectId, estimateId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/estimates/${estimateId}/send-approval-email/`,
            }),
        },
        toggleFollow: (projectId) => ({ method: 'POST', href: `${API_BASE}projects/${projectId}/toggle-follow/` }),
        followStatus: (projectId) => ({ method: 'GET',  href: `${API_BASE}projects/${projectId}/follow-status/` }),
        commentUploadImage: (projectId) => ({ method: 'POST', href: `${API_BASE}projects/${projectId}/comments/upload-image/` }),
        budgets: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/budgets/`,
            }),
            create: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/budgets/`,
            }),
            lifetime: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/budgets/lifetime/`,
            }),
            detail: (projectId, budgetId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/budgets/${budgetId}/`,
            }),
            edit: (projectId, budgetId) => ({
                method: 'PATCH',
                href: `${API_BASE}projects/${projectId}/budgets/${budgetId}/`,
            }),
            delete: (projectId, budgetId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/budgets/${budgetId}/`,
            }),
            history: (projectId, budgetId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/budgets/${budgetId}/history/`,
            }),
        },
        contacts: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/contacts/`,
            }),
            new: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/contacts/`,
            }),
            archive: (projectId, contactId) => ({
                method: 'PATCH',
                href: `${API_BASE}projects/${projectId}/contacts/${contactId}/archive/`,
            }),
        },
        links: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/links/`,
            }),
            new: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/links/`,
            }),
            update: (projectId, linkId) => ({
                method: 'PATCH',
                href: `${API_BASE}projects/${projectId}/links/${linkId}/`,
            }),
            delete: (projectId, linkId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/links/${linkId}/`,
            }),
        },
        attachments: {
            list: (projectId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/attachments/`,
            }),
            upload: (projectId) => ({
                method: 'POST',
                href: `${API_BASE}projects/${projectId}/attachments/`,
            }),
            download: (projectId, attId) => ({
                method: 'GET',
                href: `${API_BASE}projects/${projectId}/attachments/${attId}/`,
            }),
            delete: (projectId, attId) => ({
                method: 'DELETE',
                href: `${API_BASE}projects/${projectId}/attachments/${attId}/`,
            }),
        },
        views: {
            list: {
                method: 'GET',
                href: `${API_BASE}project-views/`,
            },
            new: {
                method: 'POST',
                href: `${API_BASE}project-views/`,
            },
            update: (viewId) => ({
                method: 'PATCH',
                href: `${API_BASE}project-views/${viewId}/`,
            }),
            delete: (viewId) => ({
                method: 'DELETE',
                href: `${API_BASE}project-views/${viewId}/`,
            }),
        },
    },
    users: {
        ping:          { method: 'POST', href: `${API_BASE}users/ping/` },
        mentionSearch: (q) => ({ method: 'GET', href: `${API_BASE}users/mention-search/?q=${encodeURIComponent(q)}` }),
    },
    notifications: {
        list:        { method: 'GET',  href: `${API_BASE}notifications/` },
        unreadCount: { method: 'GET',  href: `${API_BASE}notifications/unread-count/` },
        markAllRead: { method: 'POST', href: `${API_BASE}notifications/mark-all-read/` },
        detail: (id) => ({ method: 'PATCH', href: `${API_BASE}notifications/${id}/` }),
    },
    wins: {
        list:           { method: 'GET',  href: `${API_BASE}wins/` },
        create:         { method: 'POST', href: `${API_BASE}wins/` },
        nextWeek:       { method: 'GET',  href: `${API_BASE}wins/next-week/` },
        reportData:     { method: 'GET',  href: `${API_BASE}wins/report-data/` },
        detail:         (pk) => ({ method: 'GET',  href: `${API_BASE}wins/${pk}/` }),
        entries:        (pk) => ({ method: 'GET',  href: `${API_BASE}wins/${pk}/entries/` }),
        addEntry:       (pk) => ({ method: 'POST', href: `${API_BASE}wins/${pk}/entries/add/` }),
        updateEntry:    (pk) => ({ method: 'PATCH',  href: `${API_BASE}wins/entries/${pk}/` }),
        deleteEntry:    (pk) => ({ method: 'DELETE', href: `${API_BASE}wins/entries/${pk}/delete/` }),
        reviewComplete: (pk) => ({ method: 'POST', href: `${API_BASE}wins/${pk}/review-complete/` }),
    },
    monthly_wins: {
        list:              { method: 'GET',  href: `${API_BASE}monthly-wins/` },
        create:            { method: 'POST', href: `${API_BASE}monthly-wins/` },
        detail:            (pk) => ({ method: 'GET',    href: `${API_BASE}monthly-wins/${pk}/` }),
        update:            (pk) => ({ method: 'PATCH',  href: `${API_BASE}monthly-wins/${pk}/` }),
        launchPhase1:      (pk) => ({ method: 'POST',   href: `${API_BASE}monthly-wins/${pk}/launch-phase1/` }),
        completePhase1:    (pk) => ({ method: 'POST',   href: `${API_BASE}monthly-wins/${pk}/complete-phase1/` }),
        launchPhase2:      (pk) => ({ method: 'POST',   href: `${API_BASE}monthly-wins/${pk}/launch-phase2/` }),
        declare:           (pk) => ({ method: 'POST',   href: `${API_BASE}monthly-wins/${pk}/declare/` }),
        phase1Nominations: (pk) => ({ method: 'GET',    href: `${API_BASE}monthly-wins/${pk}/phase1-nominations/` }),
        surveys:           (pk) => ({ method: 'GET',    href: `${API_BASE}monthly-wins/${pk}/surveys/` }),
        remindSurvey:      (surveyPk) => ({ method: 'POST', href: `${API_BASE}monthly-wins/surveys/${surveyPk}/remind/` }),
        overrideSurvey:    (surveyPk) => ({ method: 'POST', href: `${API_BASE}monthly-wins/surveys/${surveyPk}/override/` }),
        dismissNomination: (nomPk) => ({ method: 'POST', href: `${API_BASE}monthly-wins/nominations/${nomPk}/dismiss/` }),
        undismissNomination:(nomPk) => ({ method: 'POST', href: `${API_BASE}monthly-wins/nominations/${nomPk}/undismiss/` }),
    },
    team_product_owners: {
        list:   { method: 'GET',  href: `${API_BASE}team-product-owners/` },
        create: { method: 'POST', href: `${API_BASE}team-product-owners/` },
        delete: (pk) => ({ method: 'DELETE', href: `${API_BASE}team-product-owners/${pk}/` }),
    },
    integrations: {
        ai:    { get: { method: 'GET', href: `${API_BASE}integrations/ai/` }, patch: { method: 'PATCH', href: `${API_BASE}integrations/ai/` } },
        email: { get: { method: 'GET', href: `${API_BASE}integrations/email/` }, patch: { method: 'PATCH', href: `${API_BASE}integrations/email/` } },
        sso:   { get: { method: 'GET', href: `${API_BASE}integrations/sso/` }, patch: { method: 'PATCH', href: `${API_BASE}integrations/sso/` } },
        jira:  { get: { method: 'GET', href: `${API_BASE}integrations/jira/` }, patch: { method: 'PATCH', href: `${API_BASE}integrations/jira/` } },
    },
    security: {
        get:             { method: 'GET',   href: `${API_BASE}security/` },
        patch:           { method: 'PATCH', href: `${API_BASE}security/` },
        password_policy: {
            get:   { method: 'GET',   href: `${API_BASE}security/password-policy/` },
            patch: { method: 'PATCH', href: `${API_BASE}security/password-policy/` },
        },
    },
    project_approval: {
        get:   { method: 'GET',   href: `${API_BASE}project-approval/` },
        patch: { method: 'PATCH', href: `${API_BASE}project-approval/` },
    },
    recharge_contacts: {
        get:   { method: 'GET',   href: `${API_BASE}recharge-contacts/` },
        patch: { method: 'PATCH', href: `${API_BASE}recharge-contacts/` },
    },
    configurations: {
        list: { method: 'GET', href: `${API_BASE}configurations/` },
        stats: { method: 'GET', href: `${API_BASE}configurations/stats/` },
        get: (pk) => ({ method: 'GET', href: `${API_BASE}configurations/${pk}/` }),
        default: (code) => ({
            method: 'GET',
            href: `${API_BASE}configurations/system_default/?code=${code}`,
        }),
        by_code: (code) => ({
            method: 'GET',
            href: `${API_BASE}configurations/by_code/?code=${code}`,
        }),
        detail: (pk) => ({ method: 'GET', href: `${API_BASE}configurations/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}configurations/${pk}/` }),
        export: { method: 'GET', href: `${API_BASE}configurations/export/` },
        reset: (pk) => ({ method: 'POST', href: `${API_BASE}configurations/${pk}/reset/` }),
    },
    resource_plans: {
        list: {
            method: 'GET',
            href: `${API_BASE}resource-plans/`,
        },
        detail: (planId) => ({
            method: 'GET',
            href: `${API_BASE}resource-plans/${planId}/`,
        }),
        partial_edit: (planId) => ({
            method: 'PATCH',
            href: `${API_BASE}resource-plans/${planId}/`,
        }),
        options: {
            method: 'GET',
            href: `${API_BASE}resource-plans/options/`,
        },
        create: {
            method: 'POST',
            href: `${API_BASE}resource-plans/`,
        },
        clone: (planId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${planId}/clone/`,
        }),
        archive: (planId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${planId}/archive/`,
        }),
        unarchive: (planId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${planId}/unarchive/`,
        }),
        delete: (planId) => ({
            method: 'DELETE',
            href: `${API_BASE}resource-plans/${planId}/`,
        }),
        stats: {
            method: 'GET',
            href: `${API_BASE}resource-plans/stats/`,
        },
        versions: (planId) => ({
            method: 'GET',
            href: `${API_BASE}resource-plans/${planId}/versions/`,
        }),
        version_edit: (versionPlanId) => ({
            method: 'PATCH',
            href: `${API_BASE}resource-plans/${versionPlanId}/`,
        }),
        version_activate: (versionPlanId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${versionPlanId}/activate/`,
        }),
        version_lock: (versionPlanId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${versionPlanId}/lock/`,
        }),
        version_clone: (versionPlanId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${versionPlanId}/clone/`,
        }),
        version_delete: (versionPlanId) => ({
            method: 'DELETE',
            href: `${API_BASE}resource-plans/${versionPlanId}/`,
        }),
        new_version: (planId) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${planId}/new-version/`,
        }),
        restore: (planId, sourcePk) => ({
            method: 'POST',
            href: `${API_BASE}resource-plans/${planId}/restore/${sourcePk}/`,
        }),
        comments: {
            list: (planId) => ({
                method: 'GET',
                href: `${API_BASE}resource-plans/${planId}/comments/`,
            }),
            create: (planId) => ({
                method: 'POST',
                href: `${API_BASE}resource-plans/${planId}/comments/`,
            }),
            uploadImage: (planId) => ({
                method: 'POST',
                href: `${API_BASE}resource-plans/${planId}/comments/upload-image/`,
            }),
        },
        engine: {
            run: (planId) => ({
                method: 'POST',
                href: `${API_BASE}resource-plans/${planId}/engine/run/`,
            }),
            jobs: (planId) => ({
                method: 'GET',
                href: `${API_BASE}resource-plans/${planId}/engine/jobs/`,
            }),
            job_detail: (planId, jobId) => ({
                method: 'GET',
                href: `${API_BASE}resource-plans/${planId}/engine/jobs/${jobId}/`,
            }),
            job_status: (planId, jobId) => ({
                method: 'GET',
                href: `${API_BASE}resource-plans/${planId}/engine/jobs/${jobId}/status/`,
            }),
        },
    },
    rp_versions: {
        detail: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/` }),
        allocation_sets: {
            list: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/allocation-sets/` }),
            detail: (planPk, versionPk, setId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/allocation-sets/${setId}/` }),
            update: (planPk, versionPk, setId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/allocation-sets/${setId}/` }),
            activate: (planPk, versionPk, setId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/allocation-sets/${setId}/activate/` }),
        },
        grid: {
            teams: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/teams/` }),
            capacity: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/capacity/` }),
            absences: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/absences/` }),
            allocations: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/allocations/` }),
            allocated_capacity: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/allocated-capacity/` }),
            cell_create: (planPk, versionPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/cell/` }),
            cell_update: (planPk, versionPk, allocId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/grid/cell/${allocId}/` }),
        },
        utilisation: {
            teams:      (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/utilisation/teams/` }),
            members:    (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/utilisation/members/` }),
            programmes: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/utilisation/programmes/` }),
        },
        export: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/export/` }),
        audit: {
            list:   (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/audit/` }),
            detail: (planPk, versionPk, auditPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/audit/${auditPk}/` }),
        },
        snapshots: {
            list:        (planPk, versionPk) => ({ method: 'GET',    href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/` }),
            create:      (planPk, versionPk) => ({ method: 'POST',   href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/` }),
            detail:      (planPk, versionPk, snapPk) => ({ method: 'GET',    href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/${snapPk}/` }),
            delete:      (planPk, versionPk, snapPk) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/${snapPk}/` }),
            allocations: (planPk, versionPk, snapPk) => ({ method: 'GET',    href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/${snapPk}/allocations/` }),
            capacity:    (planPk, versionPk, snapPk) => ({ method: 'GET',    href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/${snapPk}/capacity/` }),
            compare:     (planPk, versionPk, snapPk) => ({ method: 'GET',    href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/snapshots/${snapPk}/compare/` }),
        },
        conflicts: {
            list:    (planPk, versionPk) => ({ method: 'GET',  href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/conflicts/` }),
            summary: (planPk, versionPk) => ({ method: 'GET',  href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/conflicts/summary/` }),
            detail:  (planPk, versionPk, conflictPk) => ({ method: 'GET',  href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/conflicts/${conflictPk}/` }),
            resolve: (planPk, versionPk, conflictPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/conflicts/${conflictPk}/resolve/` }),
        },
        manpower: {
            list:      (planPk, versionPk) => ({ method: 'GET',  href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/manpower-requests/` }),
            detail:    (planPk, versionPk, mpPk) => ({ method: 'GET',  href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/manpower-requests/${mpPk}/` }),
            hire:      (planPk, versionPk, mpPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/manpower-requests/${mpPk}/hire/` }),
            rebalance: (planPk, versionPk, mpPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/manpower-requests/${mpPk}/rebalance/` }),
            dismiss:   (planPk, versionPk, mpPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/manpower-requests/${mpPk}/dismiss/` }),
        },
        placeholder_leaves: {
            list: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-leaves/` }),
            update: (planPk, versionPk, plPk) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-leaves/${plPk}/` }),
            delete: (planPk, versionPk, plPk) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-leaves/${plPk}/` }),
        },
        placeholder_engineers: {
            list: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/` }),
            detail: (planPk, versionPk, phPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/${phPk}/` }),
            update: (planPk, versionPk, phPk) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/${phPk}/` }),
            replace: (planPk, versionPk, phPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/${phPk}/replace/` }),
            absences: {
                list: (planPk, versionPk, phPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/${phPk}/absences/` }),
                update: (planPk, versionPk, phPk, absencePk) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/placeholder-engineers/${phPk}/absences/${absencePk}/` }),
            },
        },
        projects: {
            list: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/` }),
            create: (planPk, versionPk) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/` }),
            unmapped: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/unmapped/` }),
            options: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/options/` }),
            detail: (planPk, versionPk, entryId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/` }),
            update: (planPk, versionPk, entryId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/` }),
            delete: (planPk, versionPk, entryId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/` }),
            resync: (planPk, versionPk, entryId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/resync/` }),
            reorder: (planPk, versionPk, entryId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/reorder/` }),
        },
        teams: {
            list: (planPk, versionPk, entryId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/` }),
            create: (planPk, versionPk, entryId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/` }),
            options: (planPk, versionPk, entryId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/options/` }),
            update: (planPk, versionPk, entryId, teamEntryId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/${teamEntryId}/` }),
            delete: (planPk, versionPk, entryId, teamEntryId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/${teamEntryId}/` }),
        },
        releases: {
            list: (planPk, versionPk, entryId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/budget-releases/` }),
            create: (planPk, versionPk, entryId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/budget-releases/` }),
            update: (planPk, versionPk, entryId, releaseId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/budget-releases/${releaseId}/` }),
            delete: (planPk, versionPk, entryId, releaseId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/budget-releases/${releaseId}/` }),
        },
        phases: {
            list: (planPk, versionPk, entryId, teamEntryId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/${teamEntryId}/phases/` }),
            create: (planPk, versionPk, entryId, teamEntryId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/projects/${entryId}/teams/${teamEntryId}/phases/` }),
            options: (planPk, versionPk) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/options/` }),
            detail: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/` }),
            update: (planPk, versionPk, phaseId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/` }),
            delete: (planPk, versionPk, phaseId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/` }),
            segments: {
                list: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/` }),
                create: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/` }),
                update: (planPk, versionPk, phaseId, segId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/${segId}/` }),
                delete: (planPk, versionPk, phaseId, segId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/${segId}/` }),
                suggest: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/suggest/` }),
                reorder: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/segments/reorder/` }),
            },
            dependencies: {
                list: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/dependencies/` }),
                create: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/dependencies/` }),
                update: (planPk, versionPk, phaseId, depId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/dependencies/${depId}/` }),
                delete: (planPk, versionPk, phaseId, depId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/dependencies/${depId}/` }),
            },
            pauses: {
                list: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/pauses/` }),
                create: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/pauses/` }),
                update: (planPk, versionPk, phaseId, pauseId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/pauses/${pauseId}/` }),
                delete: (planPk, versionPk, phaseId, pauseId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/pauses/${pauseId}/` }),
            },
            assignments: {
                list: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/assignments/` }),
                create: (planPk, versionPk, phaseId) => ({ method: 'POST', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/assignments/` }),
                options: (planPk, versionPk, phaseId) => ({ method: 'GET', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/assignments/options/` }),
                update: (planPk, versionPk, phaseId, assignId) => ({ method: 'PATCH', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/assignments/${assignId}/` }),
                delete: (planPk, versionPk, phaseId, assignId) => ({ method: 'DELETE', href: `${API_BASE}resource-plans/${planPk}/versions/${versionPk}/phases/${phaseId}/assignments/${assignId}/` }),
            },
        },
    },

    finance_types: {
        list: { method: 'GET', href: `${API_BASE}finance-types/` },
        options: { method: 'GET', href: `${API_BASE}finance-types/options/` },
        create: { method: 'POST', href: `${API_BASE}finance-types/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}finance-types/${id}/` }),
        update: (id) => ({ method: 'PATCH', href: `${API_BASE}finance-types/${id}/` }),
        delete: (id) => ({ method: 'DELETE', href: `${API_BASE}finance-types/${id}/` }),
    },

    finance_type_mappings: {
        list: { method: 'GET', href: `${API_BASE}finance-type-mappings/` },
        create: { method: 'POST', href: `${API_BASE}finance-type-mappings/` },
        delete: (id) => ({ method: 'DELETE', href: `${API_BASE}finance-type-mappings/${id}/` }),
    },

    sprint_forecast: {
        list: { method: 'GET', href: `${API_BASE}sprint-forecast/` },
        import: { method: 'POST', href: `${API_BASE}sprint-forecast/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}sprint-forecast/${id}/` }),
        rows: (id) => ({ method: 'GET', href: `${API_BASE}sprint-forecast/${id}/rows/` }),
        update_row: (importId, rowId) => ({ method: 'PATCH', href: `${API_BASE}sprint-forecast/${importId}/rows/${rowId}/` }),
        add_row: (importId) => ({ method: 'POST', href: `${API_BASE}sprint-forecast/${importId}/add-row/` }),
        delete_row: (importId, rowId) => ({ method: 'DELETE', href: `${API_BASE}sprint-forecast/${importId}/rows/${rowId}/delete/` }),
        review: (id) => ({ method: 'POST', href: `${API_BASE}sprint-forecast/${id}/review/` }),
        reviews: (id) => ({ method: 'GET', href: `${API_BASE}sprint-forecast/${id}/reviews/` }),
        confirm: (id) => ({ method: 'POST', href: `${API_BASE}sprint-forecast/${id}/confirm/` }),
        labels_options: { method: 'GET', href: `${API_BASE}sprint-forecast/labels-options/` },
        sprint_status: (sprintId) => ({ method: 'GET', href: `${API_BASE}sprint-forecast/sprint-status/?sprint_id=${sprintId}` }),
        review_warnings: (sprintId) => ({ method: 'GET', href: `${API_BASE}sprint-forecast/review-warnings/?sprint_id=${sprintId}` }),
        review_complete: { method: 'POST', href: `${API_BASE}sprint-forecast/review-complete/` },
    },

    sprint_actuals: {
        list: { method: 'GET', href: `${API_BASE}sprint-actuals/` },
        import: { method: 'POST', href: `${API_BASE}sprint-actuals/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}sprint-actuals/${id}/` }),
        rows: (id) => ({ method: 'GET', href: `${API_BASE}sprint-actuals/${id}/rows/` }),
        update_row: (importId, rowId) => ({ method: 'PATCH', href: `${API_BASE}sprint-actuals/${importId}/rows/${rowId}/` }),
        add_row: (importId) => ({ method: 'POST', href: `${API_BASE}sprint-actuals/${importId}/add-row/` }),
        delete_row: (importId, rowId) => ({ method: 'DELETE', href: `${API_BASE}sprint-actuals/${importId}/rows/${rowId}/delete/` }),
        review: (id) => ({ method: 'POST', href: `${API_BASE}sprint-actuals/${id}/review/` }),
        reviews: (id) => ({ method: 'GET', href: `${API_BASE}sprint-actuals/${id}/reviews/` }),
        confirm: (id) => ({ method: 'POST', href: `${API_BASE}sprint-actuals/${id}/confirm/` }),
        labels_options: { method: 'GET', href: `${API_BASE}sprint-actuals/labels-options/` },
        sprint_status: (sprintId) => ({ method: 'GET', href: `${API_BASE}sprint-actuals/sprint-status/?sprint_id=${sprintId}` }),
        review_warnings: (sprintId) => ({ method: 'GET', href: `${API_BASE}sprint-actuals/review-warnings/?sprint_id=${sprintId}` }),
        review_complete: { method: 'POST', href: `${API_BASE}sprint-actuals/review-complete/` },
    },

    recharges: {
        list: { method: 'GET', href: `${API_BASE}recharges/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}recharges/${id}/` }),
        programme_options: { method: 'GET', href: `${API_BASE}recharges/programme-options/` },
        project_options: { method: 'GET', href: `${API_BASE}recharges/project-options/` },
        summary: (sprintId, type) => ({ method: 'GET', href: `${API_BASE}recharges/summary/?sprint_id=${sprintId}&type=${type}` }),
        email_review: { method: 'GET', href: `${API_BASE}recharges/email-review/` },
        trigger_emails: { method: 'POST', href: `${API_BASE}recharges/trigger-emails/` },
        email_status: { method: 'GET', href: `${API_BASE}recharges/email-status/` },
        resend: { method: 'POST', href: `${API_BASE}recharges/resend/` },
    },

    recharge_details: {
        list: { method: 'GET', href: `${API_BASE}recharge-details/` },
    },

    recharge_project_groups: {
        list: { method: 'GET', href: `${API_BASE}recharge-project-groups/` },
        create: { method: 'POST', href: `${API_BASE}recharge-project-groups/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}recharge-project-groups/${id}/` }),
        update: (id) => ({ method: 'PATCH', href: `${API_BASE}recharge-project-groups/${id}/` }),
        delete: (id) => ({ method: 'DELETE', href: `${API_BASE}recharge-project-groups/${id}/` }),
        project_options: { method: 'GET', href: `${API_BASE}recharge-project-groups/project-options/` },
    },

    sprint_compare: {
        data: (sprintId) => ({ method: 'GET', href: `${API_BASE}sprint-compare/?sprint_id=${sprintId}` }),
    },

    email_templates: {
        scenarios: { method: 'GET', href: `${API_BASE}email-templates/` },
        detail: (scenario) => ({ method: 'GET', href: `${API_BASE}email-templates/${scenario}/` }),
        save:   (scenario) => ({ method: 'PUT', href: `${API_BASE}email-templates/${scenario}/` }),
        variables: (scenario) => ({ method: 'GET', href: `${API_BASE}email-templates/${scenario}/variables/` }),
    },
    email_template_headers: {
        list:    { method: 'GET',    href: `${API_BASE}email-template-headers/` },
        options: { method: 'GET',    href: `${API_BASE}email-template-headers/options/` },
        create:  { method: 'POST',   href: `${API_BASE}email-template-headers/` },
        detail:  (id) => ({ method: 'GET',    href: `${API_BASE}email-template-headers/${id}/` }),
        update:  (id) => ({ method: 'PATCH',  href: `${API_BASE}email-template-headers/${id}/` }),
        delete:  (id) => ({ method: 'DELETE', href: `${API_BASE}email-template-headers/${id}/` }),
    },
    email_template_footers: {
        list:    { method: 'GET',    href: `${API_BASE}email-template-footers/` },
        options: { method: 'GET',    href: `${API_BASE}email-template-footers/options/` },
        create:  { method: 'POST',   href: `${API_BASE}email-template-footers/` },
        detail:  (id) => ({ method: 'GET',    href: `${API_BASE}email-template-footers/${id}/` }),
        update:  (id) => ({ method: 'PATCH',  href: `${API_BASE}email-template-footers/${id}/` }),
        delete:  (id) => ({ method: 'DELETE', href: `${API_BASE}email-template-footers/${id}/` }),
    },
    business_units: {
        list:    { method: 'GET',    href: `${API_BASE}business-units/` },
        stats:   { method: 'GET',    href: `${API_BASE}business-units/stats/` },
        options: { method: 'GET',    href: `${API_BASE}business-units/options/` },
        create:  { method: 'POST',   href: `${API_BASE}business-units/` },
        detail:  (pk) => ({ method: 'GET',    href: `${API_BASE}business-units/${pk}/` }),
        update:  (pk) => ({ method: 'PATCH',  href: `${API_BASE}business-units/${pk}/` }),
        delete:  (pk) => ({ method: 'DELETE', href: `${API_BASE}business-units/${pk}/` }),
    },

    project_actuals: {
        list: { method: 'GET', href: `${API_BASE}project-actuals/` },
        detail: (id) => ({ method: 'GET', href: `${API_BASE}project-actuals/${id}/` }),
        patch: (id) => ({ method: 'PATCH', href: `${API_BASE}project-actuals/${id}/` }),
        fy_options: { method: 'GET', href: `${API_BASE}project-actuals/fy-options/` },
        project_options: (programmeId) => ({
            method: 'GET',
            href: `${API_BASE}project-actuals/project-options/${programmeId ? `?programme_id=${programmeId}` : ''}`,
        }),
        team_options: { method: 'GET', href: `${API_BASE}project-actuals/team-options/` },
        fy_sprints: (fyId) => ({ method: 'GET', href: `${API_BASE}project-actuals/fy-sprints/?fy_id=${fyId}` }),
        copy_from_previous_fy: { method: 'POST', href: `${API_BASE}project-actuals/copy-from-previous-fy/` },
        mark_complete: (id) => ({ method: 'POST', href: `${API_BASE}project-actuals/${id}/mark-complete/` }),
    },
};

export const URLS = {
    delivery_teams: {
        list: '/delivery-teams/',
        new: '/delivery-teams/new/',
        detail: (pk) => `/delivery-teams/${pk}/`,
        edit: (pk) => `/delivery-teams/${pk}/edit/`,
        delete: (pk) => `/delivery-teams/${pk}/delete/`,
        import: '/delivery-teams/import/',
        import_sample: '/delivery-teams/import/sample/',
    },
    skills: {
        list: '/skills/',
        new: '/skills/new/',
        detail: (pk) => `/skills/${pk}/`,
        edit: (pk) => `/skills/${pk}/edit/`,
        delete: (pk) => `/skills/${pk}/delete/`,
        import: '/skills/import/',
        import_sample: '/skills/import/sample/',
    },
    locations: {
        list: '/locations/',
        new: '/locations/new/',
        detail: (pk) => `/locations/${pk}/`,
        edit: (pk) => `/locations/${pk}/edit/`,
        delete: (pk) => `/locations/${pk}/delete/`,
        import: '/locations/import/',
        import_sample: '/locations/import/sample/',
    },
    roles: {
        list: '/roles/',
        new: '/roles/new/',
        detail: (pk) => `/roles/${pk}/`,
        edit: (pk) => `/roles/${pk}/edit/`,
        delete: (pk) => `/roles/${pk}/delete/`,
        import: '/roles/import/',
        import_sample: '/roles/import/sample/',
    },
    employment_types: {
        list: '/employment-types/',
        new: '/employment-types/new/',
        detail: (pk) => `/employment-types/${pk}/`,
        edit: (pk) => `/employment-types/${pk}/edit/`,
        delete: (pk) => `/employment-types/${pk}/delete/`,
        import: '/employment-types/import/',
        import_sample: '/employment-types/import/sample/',
    },
    team_members: {
        list: '/team-members/',
        new: '/team-members/new/',
        detail: (pk) => `/team-members/${pk}/`,
        edit: (pk) => `/team-members/${pk}/edit/`,
        delete: (pk) => `/team-members/${pk}/delete/`,
        import: '/team-members/import/',
        import_sample: '/team-members/import/sample/',
    },
    holidays: {
        list: '/holidays/',
        new: '/holidays/new/',
        detail: (pk) => `/holidays/${pk}/`,
        edit: (pk) => `/holidays/${pk}/edit/`,
        delete: (pk) => `/holidays/${pk}/delete/`,
        import: '/holidays/import/',
        import_sample: '/holidays/import/sample/',
    },
    leaves: {
        list: '/leaves/',
        new: '/leaves/new/',
        detail: (pk) => `/leaves/${pk}/`,
        edit: (pk) => `/leaves/${pk}/edit/`,
        delete: (pk) => `/leaves/${pk}/delete/`,
        import: '/leaves/import/',
        import_sample: '/leaves/import/sample/',
    },
    financial_years: {
        list: '/fy/',
        new: '/fy/new/',
        detail: (pk) => `/fy/${pk}/`,
        edit: (pk) => `/fy/${pk}/edit/`,
        delete: (pk) => `/fy/${pk}/delete/`,
        import: '/fy/import/',
        import_sample: '/fy/import/sample/',
    },
    sprints: {
        list: '/sprints/',
        new: '/sprints/new/',
        detail: (pk) => `/sprints/${pk}/`,
        edit: (pk) => `/sprints/${pk}/edit/`,
        delete: (pk) => `/sprints/${pk}/delete/`,
        compare: (pk) => `/sprints/${pk}/compare/`,
    },
    project_actuals: {
        list: '/project-actuals/',
    },
    recharges: {
        list: '/recharges/',
        sprint: (sprintId) => `/recharges/${sprintId}/`,
        review_forecast: (sprintId) => `/recharges/${sprintId}/forecast/`,
        review_actuals: (sprintId) => `/recharges/${sprintId}/actuals/`,
    },
    project_types: {
        list: '/project-types/',
        new: '/project-types/new/',
        detail: (pk) => `/project-types/${pk}/`,
        edit: (pk) => `/project-types/${pk}/edit/`,
        delete: (pk) => `/project-types/${pk}/delete/`,
        import: '/project-types/import/',
        import_sample: '/project-types/import/sample/',
    },
    project_sub_statuses: {
        list: '/project-sub-statuses/',
        new: '/project-sub-statuses/new/',
        detail: (pk) => `/project-sub-statuses/${pk}/`,
        edit: (pk) => `/project-sub-statuses/${pk}/edit/`,
        delete: (pk) => `/project-sub-statuses/${pk}/delete/`,
        import: '/project-sub-statuses/import/',
        import_sample: '/project-sub-statuses/import/sample/',
    },
    programmes: {
        list: '/programmes/',
        import_sample: '/programmes/import/sample/',
    },
    contacts: {
        list: '/contacts/',
        import_sample: '/contacts/import/sample/',
    },
    projects: {
        list: '/projects/',
        detail: (pk) => `/projects/${pk}/`,
        import_sample: '/projects/import/sample/',
    },
    configurations: {
        list: '/configurations/',
        detail: (pk) => `/configurations/${pk}/`,
        edit: (pk) => `/configurations/${pk}/edit/`,
    },
    integrations: {
        ai:    '/integrations/ai/',
        email: '/integrations/email/',
        sso:   '/integrations/sso/',
        jira:  '/integrations/jira/',
    },
    security: {
        list:             '/security/',
        password_policy:  '/security/password-policy/',
    },
    project_approval: {
        list: '/project-approval/',
    },
    recharge_contacts: {
        list: '/recharge-contacts/',
    },
    email_templates: {
        list:    '/email-templates/',
        editor:  (scenario) => `/email-templates/${scenario}/editor/`,
        headers: '/email-templates/headers/',
        footers: '/email-templates/footers/',
    },
    resource_plans: {
        detail: (planId) => `/resource-plans/${planId}`,
        allocation_grid: (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/grid/`,
        placeholder_leaves: (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/placeholder-leaves/`,
        conflicts: (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/conflicts/`,
        utilisation: (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/utilisation/`,
        snapshots:  (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/snapshots/`,
        audit_log:  (planId, versionId) => `/resource-plans/${planId}/versions/${versionId}/audit/`,
    },
};
