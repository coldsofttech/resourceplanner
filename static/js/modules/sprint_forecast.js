'use strict';

import { API_URLS } from '../urls.js';
import { initImportPage } from './sprint_import_page.js';

const SPRINT_ID = window.SPRINT_ID;

initImportPage({
    sprintId: SPRINT_ID,
    apiNs: API_URLS.sprint_forecast,
    detailUrlFn: (id) => `/sprints/${SPRINT_ID}/forecast/${id}/`,
});
