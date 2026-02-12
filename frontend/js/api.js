/**
 * API Client for Job Application Tracker
 */

const API_BASE = '';

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const cfg = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (cfg.body && typeof cfg.body === 'object') {
            cfg.body = JSON.stringify(cfg.body);
        }

        try {
            const response = await fetch(url, cfg);
            const data = await response.json();

            if (response.status === 401 && endpoint !== '/auth/login' && endpoint !== '/auth/status') {
                if (typeof app !== 'undefined' && app.showLoginScreen) {
                    app.showLoginScreen();
                }
                throw new Error('Authentication required');
            }

            if (!response.ok) {
                throw new Error(data.error || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // App authentication
    async checkAuthStatus() {
        return this.request('/auth/status');
    }

    async login(password) {
        return this.request('/auth/login', {
            method: 'POST',
            body: { password }
        });
    }

    async appLogout() {
        return this.request('/auth/logout', { method: 'POST' });
    }

    // Auth endpoints
    async getGmailAuthUrl() {
        return this.request('/auth/gmail/login');
    }

    async getGmailStatus() {
        return this.request('/auth/gmail/status');
    }

    async disconnectGmail() {
        return this.request('/auth/gmail/disconnect', { method: 'POST' });
    }

    // Applications
    async getApplications(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/applications${query ? '?' + query : ''}`);
    }

    async getApplication(id) {
        return this.request(`/api/applications/${id}`);
    }

    async createApplication(data) {
        return this.request('/api/applications', {
            method: 'POST',
            body: data
        });
    }

    async updateApplication(id, data) {
        return this.request(`/api/applications/${id}`, {
            method: 'PUT',
            body: data
        });
    }

    async deleteApplication(id) {
        return this.request(`/api/applications/${id}`, {
            method: 'DELETE'
        });
    }

    async autoRejectStale(options = {}) {
        return this.request('/api/applications/auto-reject-stale', {
            method: 'POST',
            body: options
        });
    }

    async updateApplicationStatus(id, status) {
        return this.request(`/api/applications/${id}/status`, {
            method: 'PATCH',
            body: { status }
        });
    }

    // Emails
    async scanEmails(options = {}) {
        return this.request('/api/emails/scan', {
            method: 'POST',
            body: options
        });
    }

    async getUnprocessedEmails() {
        return this.request('/api/emails/unprocessed');
    }

    async linkEmailToApplication(emailId, applicationId) {
        return this.request(`/api/emails/${emailId}/link`, {
            method: 'POST',
            body: { application_id: applicationId }
        });
    }

    async createApplicationFromEmail(emailId, data = {}) {
        return this.request(`/api/emails/${emailId}/create-application`, {
            method: 'POST',
            body: data
        });
    }

    async dismissEmail(emailId) {
        return this.request(`/api/emails/${emailId}/dismiss`, {
            method: 'POST'
        });
    }

    async autoProcessEmails(options = {}) {
        return this.request('/api/emails/auto-process', {
            method: 'POST',
            body: options
        });
    }

    // Reminders
    async getReminders(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/reminders${query ? '?' + query : ''}`);
    }

    async getDueReminders() {
        return this.request('/api/reminders/due');
    }

    async createReminder(data) {
        return this.request('/api/reminders', {
            method: 'POST',
            body: data
        });
    }

    async completeReminder(id) {
        return this.request(`/api/reminders/${id}/complete`, {
            method: 'POST'
        });
    }

    async dismissReminder(id) {
        return this.request(`/api/reminders/${id}/dismiss`, {
            method: 'POST'
        });
    }

    async snoozeReminder(id, days = 1) {
        return this.request(`/api/reminders/${id}/snooze`, {
            method: 'POST',
            body: { days }
        });
    }

    async autoCreateReminders(options = {}) {
        return this.request('/api/reminders/auto-create', {
            method: 'POST',
            body: options
        });
    }

    // Stats
    async getDashboardStats() {
        return this.request('/api/stats/dashboard');
    }

    async getStatusBreakdown() {
        return this.request('/api/stats/status-breakdown');
    }

    async getTimeline(days = 30) {
        return this.request(`/api/stats/timeline?days=${days}`);
    }

    async getResponseRates() {
        return this.request('/api/stats/response-rates');
    }

    // Interviews
    async getInterviews(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/api/interviews${query ? '?' + query : ''}`);
    }

    async getUpcomingInterviews(limit = 10) {
        return this.request(`/api/interviews/upcoming?limit=${limit}`);
    }

    async getInterview(id) {
        return this.request(`/api/interviews/${id}`);
    }

    async createInterview(data) {
        return this.request('/api/interviews', {
            method: 'POST',
            body: data
        });
    }

    async updateInterview(id, data) {
        return this.request(`/api/interviews/${id}`, {
            method: 'PUT',
            body: data
        });
    }

    async deleteInterview(id) {
        return this.request(`/api/interviews/${id}`, {
            method: 'DELETE'
        });
    }

    async cancelInterview(id) {
        return this.request(`/api/interviews/${id}/cancel`, {
            method: 'POST'
        });
    }

    async updateInterviewNotes(id, data) {
        return this.request(`/api/interviews/${id}/notes`, {
            method: 'PUT',
            body: data
        });
    }
}

// Export singleton instance
const api = new ApiClient();
