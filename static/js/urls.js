'use strict';

const API_BASE = '/api/v1/';

export const API_URLS = {
    delivery_teams: {
        list:       { method: 'GET', href: `${API_BASE}delivery-teams/` },
        stats:      { method: 'GET', href: `${API_BASE}delivery-teams/stats/` },
        new:        { method: 'POST', href: `${API_BASE}delivery-teams/` },
        get:        (pk) => ({ method: 'GET', href: `${API_BASE}delivery-teams/${pk}/` }),
        detail:     (pk) => ({ method: 'GET', href: `${API_BASE}delivery-teams/${pk}/` }),
        edit:       (pk) => ({ method: 'PUT', href: `${API_BASE}delivery-teams/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}delivery-teams/${pk}/` }),
        delete:     (pk) => ({ method: 'DELETE', href: `${API_BASE}delivery-teams/${pk}/` }),
        options:    { method: 'GET', href: `${API_BASE}delivery-teams/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}delivery-teams/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}delivery-teams/import/sample/` },
        import:     { method: 'POST', href: `${API_BASE}delivery-teams/import/` },
        export:     { method: 'GET', href: `${API_BASE}delivery-teams/export/` },
    },
    skills: {
        list:       { method: 'GET', href: `${API_BASE}skills/` },
        stats:      { method: 'GET', href: `${API_BASE}skills/stats/` },
        new:        { method: 'POST', href: `${API_BASE}skills/` },
        get:        (pk) => ({ method: 'GET', href: `${API_BASE}skills/${pk}/` }),
        detail:     (pk) => ({ method: 'GET', href: `${API_BASE}skills/${pk}/` }),
        edit:       (pk) => ({ method: 'PUT', href: `${API_BASE}skills/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}skills/${pk}/` }),
        delete:     (pk) => ({ method: 'DELETE', href: `${API_BASE}skills/${pk}/` }),
        options:    { method: 'GET', href: `${API_BASE}skills/options/` },
        import_spec: { method: 'GET', href: `${API_BASE}skills/import/specifications/` },
        import_sample: { method: 'GET', href: `${API_BASE}skills/import/sample/` },
        import:     { method: 'POST', href: `${API_BASE}skills/import/` },
        export:     { method: 'GET', href: `${API_BASE}skills/export/` },
    },
    configurations: {
        list:       { method: 'GET', href: `${API_BASE}configurations/` },
        stats:      { method: 'GET', href: `${API_BASE}configurations/stats/` },
        get:        (pk) => ({ method: 'GET', href: `${API_BASE}configurations/${pk}/` }),
        default:    (code) => ({ method: 'GET', href: `${API_BASE}configurations/system_default/?code=${code}` }),
        by_code:    (code) => ({ method: 'GET', href: `${API_BASE}configurations/by_code/?code=${code}` }),
        detail:     (pk) => ({ method: 'GET', href: `${API_BASE}configurations/${pk}/` }),
        partial_edit: (pk) => ({ method: 'PATCH', href: `${API_BASE}configurations/${pk}/` }),
        export:     { method: 'GET', href: `${API_BASE}configurations/export/` },
        reset:      (pk) => ({ method: 'POST', href: `${API_BASE}configurations/${pk}/reset/` })
    }
};

export const URLS = {
    delivery_teams: {
        list:       '/delivery-teams/',
        new:        '/delivery-teams/new/',
        detail:     (pk) => `/delivery-teams/${pk}/`,
        edit:       (pk) => `/delivery-teams/${pk}/edit/`,
        delete:     (pk) => `/delivery-teams/${pk}/delete/`,
        import:     '/delivery-teams/import/',
        import_sample: '/delivery-teams/import/sample/',
    },
    skills: {
        list:       '/skills/',
        new:        '/skills/new/',
        detail:     (pk) => `/skills/${pk}/`,
        edit:       (pk) => `/skills/${pk}/edit/`,
        delete:     (pk) => `/skills/${pk}/delete/`,
        import:     '/skills/import/',
        import_sample: '/skills/import/sample/',
    },
    configurations: {
        list:       '/configurations/',
        detail:     (pk) => `/configurations/${pk}/`,
        edit:       (pk) => `/configurations/${pk}/edit/`,
    }
}