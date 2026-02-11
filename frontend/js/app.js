/**
 * Job Application Tracker - Main Application
 */

class JobTrackerApp {
    constructor() {
        this.currentView = 'dashboard';
        this.applications = [];
        this.currentPage = 1;
        this.perPage = 20;
        this.totalPages = 1;
        this.searchTerm = '';
        this.statusFilter = '';
        this._interviewCache = {};

        this.init();
    }

    async init() {
        this.bindEvents();
        // Check app authentication before loading data
        const authed = await this.checkAppAuth();
        if (!authed) return;
        this.checkUrlParams();
        await this.checkGmailStatus();
        await this.loadDashboard();
    }

    async checkAppAuth() {
        try {
            const status = await api.checkAuthStatus();
            if (!status.auth_required || status.authenticated) {
                this.hideLoginScreen();
                return true;
            }
            this.showLoginScreen();
            return false;
        } catch {
            this.showLoginScreen();
            return false;
        }
    }

    showLoginScreen() {
        let overlay = document.getElementById('login-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'login-overlay';
            overlay.innerHTML = `
                <div class="login-card">
                    <div class="login-logo"><span class="logo-icon">&#9672;</span> JobTrack</div>
                    <form id="login-form">
                        <div class="form-group">
                            <label for="login-password">Password</label>
                            <input type="password" id="login-password" placeholder="Enter password" required autofocus>
                        </div>
                        <div id="login-error" class="login-error" style="display:none;"></div>
                        <button type="submit" class="btn-primary" style="width:100%;">Log In</button>
                    </form>
                </div>
            `;
            document.body.appendChild(overlay);
            document.getElementById('login-form').addEventListener('submit', (e) => this.handleLogin(e));
        }
        overlay.style.display = 'flex';
    }

    hideLoginScreen() {
        const overlay = document.getElementById('login-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    async handleLogin(e) {
        e.preventDefault();
        const pw = document.getElementById('login-password').value;
        const errEl = document.getElementById('login-error');
        errEl.style.display = 'none';

        try {
            await api.login(pw);
            this.hideLoginScreen();
            this.checkUrlParams();
            await this.checkGmailStatus();
            await this.loadDashboard();
        } catch (err) {
            errEl.textContent = 'Invalid password';
            errEl.style.display = 'block';
        }
    }

    bindEvents() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                this.switchView(view);
            });
        });

        // Gmail connection
        document.getElementById('btn-connect-gmail').addEventListener('click', () => this.connectGmail());

        // Applications
        document.getElementById('btn-add-application').addEventListener('click', () => this.openApplicationModal());
        document.getElementById('search-input').addEventListener('input', debounce((e) => {
            this.searchTerm = e.target.value;
            this.currentPage = 1;
            this.loadApplications();
        }, 300));
        document.getElementById('status-filter').addEventListener('change', (e) => {
            this.statusFilter = e.target.value;
            this.currentPage = 1;
            this.loadApplications();
        });

        // Application form
        document.getElementById('application-form').addEventListener('submit', (e) => this.handleApplicationSubmit(e));
        
        // Show/hide rejected stage field based on status
        document.getElementById('app-status').addEventListener('change', (e) => this.toggleRejectedStageField(e.target.value));
        
        // Fetch job description button
        document.getElementById('btn-fetch-description').addEventListener('click', () => this.fetchJobDescription());

        // Emails
        document.getElementById('btn-scan-emails').addEventListener('click', () => this.scanEmails());
        document.getElementById('btn-auto-process').addEventListener('click', () => this.autoProcessEmails());

        // Reminders
        document.getElementById('btn-auto-reminders').addEventListener('click', () => this.autoCreateReminders());
        document.getElementById('reminder-form').addEventListener('submit', (e) => this.handleReminderSubmit(e));

        // Interviews
        document.getElementById('interview-form').addEventListener('submit', (e) => this.handleInterviewSubmit(e));
        document.getElementById('interview-notes-form').addEventListener('submit', (e) => this.handleInterviewNotesSubmit(e));
        
        // Interview notes tabs
        document.querySelectorAll('.notes-tabs .tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchNotesTab(e.target.dataset.tab));
        });
        
        // Application detail modal buttons
        document.getElementById('btn-add-interview-detail')?.addEventListener('click', () => {
            const appId = document.getElementById('application-detail-modal').dataset.appId;
            if (appId) this.openInterviewModal(parseInt(appId));
        });
        document.getElementById('btn-edit-from-detail')?.addEventListener('click', () => {
            const appId = document.getElementById('application-detail-modal').dataset.appId;
            if (appId) {
                this.closeModals();
                this.editApplication(parseInt(appId));
            }
        });

        // Modal close handlers
        document.querySelectorAll('.modal-close, .modal-cancel, .modal-overlay').forEach(el => {
            el.addEventListener('click', () => this.closeModals());
        });

        // Prevent modal content click from closing
        document.querySelectorAll('.modal-content').forEach(el => {
            el.addEventListener('click', (e) => e.stopPropagation());
        });
    }

    checkUrlParams() {
        const params = new URLSearchParams(window.location.search);
        if (params.get('auth_success')) {
            this.showToast('Gmail connected successfully!', 'success');
            window.history.replaceState({}, '', '/');
        } else if (params.get('auth_error')) {
            this.showToast('Gmail connection failed. Please try again.', 'error');
            window.history.replaceState({}, '', '/');
        }
    }

    async checkGmailStatus() {
        try {
            const status = await api.getGmailStatus();
            this.updateGmailStatus(status.connected);
        } catch (error) {
            console.error('Failed to check Gmail status:', error);
        }
    }

    updateGmailStatus(connected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        const connectBtn = document.getElementById('btn-connect-gmail');

        if (connected) {
            statusDot.classList.add('connected');
            statusText.textContent = 'Gmail Connected';
            connectBtn.textContent = 'Disconnect';
            connectBtn.onclick = () => this.disconnectGmail();
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = 'Gmail Disconnected';
            connectBtn.textContent = 'Connect Gmail';
            connectBtn.onclick = () => this.connectGmail();
        }
    }

    async connectGmail() {
        try {
            const { auth_url } = await api.getGmailAuthUrl();
            window.location.href = auth_url;
        } catch (error) {
            this.showToast('Failed to connect Gmail: ' + error.message, 'error');
        }
    }

    async disconnectGmail() {
        try {
            await api.disconnectGmail();
            this.updateGmailStatus(false);
            this.showToast('Gmail disconnected', 'info');
        } catch (error) {
            this.showToast('Failed to disconnect Gmail', 'error');
        }
    }

    switchView(view) {
        this.currentView = view;

        // Update nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.view === view);
        });

        // Update views
        document.querySelectorAll('.view').forEach(v => {
            v.classList.toggle('active', v.id === `view-${view}`);
        });

        // Load view data
        switch (view) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'applications':
                this.loadApplications();
                break;
            case 'emails':
                this.loadEmails();
                break;
            case 'reminders':
                this.loadReminders();
                break;
        }
    }

    // ==========================================
    // Dashboard
    // ==========================================

    async loadDashboard() {
        try {
            const stats = await api.getDashboardStats();
            this.renderDashboard(stats);
        } catch (error) {
            console.error('Failed to load dashboard:', error);
        }
    }

    renderDashboard(stats) {
        // Overview stats
        document.getElementById('stat-total').textContent = stats.overview.total_applications;
        document.getElementById('stat-active').textContent = stats.overview.active_applications;
        document.getElementById('stat-rejected').textContent = stats.overview.rejected;
        document.getElementById('stat-interviews').textContent = stats.overview.interviews;
        document.getElementById('stat-offers').textContent = stats.overview.offers;

        // Interview funnel
        this.renderInterviewFunnel(stats.interview_funnel, stats.overview.total_applications);
        
        // Rejection breakdown
        this.renderRejectionBreakdown(stats.rejection_breakdown);

        // Response rates
        this.renderRateCircle('rate-response', stats.response_rates.response_rate);
        this.renderRateCircle('rate-interview', stats.response_rates.interview_rate);
        this.renderRateCircle('rate-offer', stats.response_rates.offer_rate);
        
        const avgDays = document.getElementById('avg-days');
        avgDays.querySelector('.days-value').textContent = stats.response_rates.avg_response_days ?? '--';

        // Status breakdown
        this.renderStatusBars(stats.status_breakdown);

        // Recent activity
        this.renderRecentActivity(stats.recent_activity);
    }

    renderRateCircle(id, value) {
        const container = document.getElementById(id);
        const fill = container.querySelector('.rate-fill');
        const valueEl = container.querySelector('.rate-value');
        
        fill.setAttribute('stroke-dasharray', `${value}, 100`);
        valueEl.textContent = `${value}%`;
    }

    renderStatusBars(breakdown) {
        const container = document.getElementById('status-bars');
        const maxCount = Math.max(...breakdown.map(b => b.count), 1);
        
        const relevantStatuses = breakdown.filter(b => b.count > 0).slice(0, 8);
        
        if (relevantStatuses.length === 0) {
            container.innerHTML = '<p class="empty-state">No data yet</p>';
            return;
        }
        
        container.innerHTML = relevantStatuses.map(item => {
            const widthPct = Math.min((item.count / maxCount) * 100, 100);
            const safeColor = /^#[0-9a-fA-F]{3,8}$/.test(item.color) ? item.color : '#888';
            return `
            <div class="status-bar-item">
                <span class="status-bar-label">${this.escapeHtml(item.label)}</span>
                <div class="status-bar-track">
                    <div class="status-bar-fill" style="width: ${widthPct}%; background: ${safeColor}"></div>
                </div>
                <span class="status-bar-count">${parseInt(item.count) || 0}</span>
            </div>
        `;
        }).join('');
    }

    renderInterviewFunnel(funnel, total) {
        const container = document.getElementById('interview-funnel');
        
        if (!funnel || funnel.length === 0 || total === 0) {
            container.innerHTML = '<p class="empty-state">No data yet. Add applications to see your interview funnel.</p>';
            return;
        }
        
        const stageColors = {
            'Applied': '#3B82F6',
            'Phone Screen': '#6366F1',
            'First Interview': '#8B5CF6',
            'Second Interview': '#A855F7',
            'Third Interview': '#EC4899',
            'Offer': '#22C55E'
        };
        
        const stageIcons = {
            'Applied': '📝',
            'Phone Screen': '📞',
            'First Interview': '1️⃣',
            'Second Interview': '2️⃣',
            'Third Interview': '3️⃣',
            'Offer': '🎉'
        };
        
        // Calculate how many advanced to next stage
        const stagesWithFlow = funnel.map((stage, index) => {
            const nextStage = funnel[index + 1];
            const advancedToNext = nextStage ? nextStage.reached : stage.reached; // For last stage, all "advanced" (got offer)
            const rejectedHere = stage.rejected_here || 0;
            const stillInProgress = index === funnel.length - 1 ? stage.current : 0;
            
            return {
                ...stage,
                advancedToNext,
                rejectedHere,
                stillInProgress
            };
        });
        
        container.innerHTML = `
            <div class="funnel-table">
                <div class="funnel-header">
                    <span class="funnel-col-stage">Stage</span>
                    <span class="funnel-col-reached">Reached</span>
                    <span class="funnel-col-advanced">✓ Advanced</span>
                    <span class="funnel-col-rejected">✕ Rejected</span>
                    <span class="funnel-col-rate">Pass Rate</span>
                </div>
                ${stagesWithFlow.map((stage, index) => {
                    const nextStage = stagesWithFlow[index + 1];
                    const advanced = nextStage ? nextStage.reached : (stage.current || 0);
                    const rejected = stage.rejectedHere;
                    const passRate = stage.reached > 0 ? Math.round((advanced / stage.reached) * 100) : 0;
                    const isLastStage = index === stagesWithFlow.length - 1;
                    
                    return `
                        <div class="funnel-row ${stage.reached === 0 ? 'empty' : ''}">
                            <span class="funnel-col-stage">
                                <span class="funnel-icon">${stageIcons[stage.stage] || '•'}</span>
                                ${stage.stage}
                            </span>
                            <span class="funnel-col-reached">${stage.reached}</span>
                            <span class="funnel-col-advanced ${advanced > 0 ? 'has-value' : ''}">${isLastStage ? (stage.current > 0 ? stage.current + ' 🎉' : '-') : advanced}</span>
                            <span class="funnel-col-rejected ${rejected > 0 ? 'has-value' : ''}">${rejected > 0 ? rejected : '-'}</span>
                            <span class="funnel-col-rate">
                                ${stage.reached > 0 && !isLastStage ? `
                                    <span class="pass-rate-bar">
                                        <span class="pass-rate-fill ${passRate >= 50 ? 'good' : passRate >= 25 ? 'medium' : 'low'}" style="width: ${passRate}%"></span>
                                    </span>
                                    <span class="pass-rate-value">${passRate}%</span>
                                ` : '-'}
                            </span>
                        </div>
                    `;
                }).join('')}
            </div>
            <div class="funnel-legend">
                <span><strong>Reached:</strong> Applications that got to this stage</span>
                <span><strong>Advanced:</strong> Moved to next stage</span>
                <span><strong>Rejected:</strong> Rejected at this stage</span>
            </div>
        `;
    }

    renderRejectionBreakdown(rejection) {
        const summaryContainer = document.getElementById('rejection-summary');
        const stagesContainer = document.getElementById('rejection-stages');
        
        if (!rejection || rejection.total_rejected === 0) {
            summaryContainer.innerHTML = `<p class="no-rejections">🎉 No rejections yet! Keep going!</p>`;
            stagesContainer.innerHTML = '';
            return;
        }
        
        summaryContainer.innerHTML = `
            <div class="rejection-total">
                <span class="rejection-number">${rejection.total_rejected}</span>
                <span class="rejection-label">Total Rejections</span>
            </div>
        `;
        
        if (rejection.by_stage.length === 0) {
            stagesContainer.innerHTML = '<p class="empty-state">No rejection stages recorded yet. Update your rejected applications with the stage info.</p>';
            return;
        }
        
        const maxCount = Math.max(...rejection.by_stage.map(s => s.count), 1);
        
        stagesContainer.innerHTML = rejection.by_stage.map(stage => `
            <div class="rejection-stage-item">
                <div class="rejection-stage-header">
                    <span class="rejection-stage-name">${this.escapeHtml(stage.stage)}</span>
                    <span class="rejection-stage-count">${stage.count} (${stage.percentage}%)</span>
                </div>
                <div class="rejection-stage-bar">
                    <div class="rejection-stage-fill" style="width: ${(stage.count / maxCount) * 100}%"></div>
                </div>
            </div>
        `).join('');
    }

    renderRecentActivity(activity) {
        const container = document.getElementById('recent-activity');
        
        if (!activity || activity.length === 0) {
            container.innerHTML = '<p class="empty-state">No applications yet. Add your first one!</p>';
            return;
        }

        container.innerHTML = activity.slice(0, 5).map(app => `
            <div class="activity-item">
                <span class="activity-status status-badge status-${app.status}">${this.formatStatus(app.status)}</span>
                <div class="activity-content">
                    <div class="activity-company">${this.escapeHtml(app.company_name)}</div>
                    <div class="activity-position">${this.escapeHtml(app.position_title)}</div>
                </div>
                <span class="activity-date">${this.formatDate(app.updated_at)}</span>
            </div>
        `).join('');
    }

    // ==========================================
    // Applications
    // ==========================================

    async loadApplications() {
        try {
            const params = {
                page: this.currentPage,
                per_page: this.perPage
            };
            
            if (this.searchTerm) params.search = this.searchTerm;
            if (this.statusFilter) params.status = this.statusFilter;

            const data = await api.getApplications(params);
            this.applications = data.applications;
            this.totalPages = data.pages;
            
            this.renderApplications();
            this.renderPagination(data);
            
            document.getElementById('app-count').textContent = `${data.total} application${data.total !== 1 ? 's' : ''}`;
        } catch (error) {
            console.error('Failed to load applications:', error);
            this.showToast('Failed to load applications', 'error');
        }
    }

    renderApplications() {
        const tbody = document.getElementById('applications-tbody');
        
        if (this.applications.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">No applications found</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.applications.map(app => `
            <tr data-id="${app.id}">
                <td class="company-cell clickable" onclick="app.openApplicationDetail(${app.id})">${this.escapeHtml(app.company_name)}</td>
                <td class="position-cell">${this.escapeHtml(app.position_title)}</td>
                <td>
                    <span class="status-badge status-${app.status}">${this.formatStatus(app.status)}</span>
                    ${app.rejected_at_stage ? `<div class="rejected-stage">${this.escapeHtml(app.rejected_at_stage)}</div>` : ''}
                </td>
                <td class="date-cell">${this.formatDate(app.applied_date)}</td>
                <td class="date-cell">${app.updated_at ? this.formatDateTime(app.updated_at) : '-'}</td>
                <td class="actions-cell">
                    <button class="btn-icon" onclick="app.editApplication(${app.id})" title="Edit">✎</button>
                    <button class="btn-icon" onclick="app.openInterviewModal(${app.id})" title="Schedule Interview">📅</button>
                    <button class="btn-icon" onclick="app.openReminderModal(${app.id})" title="Set Reminder">⏰</button>
                    <button class="btn-icon danger" onclick="app.deleteApplication(${app.id})" title="Delete">✕</button>
                </td>
            </tr>
        `).join('');
    }

    renderPagination(data) {
        const container = document.getElementById('pagination');
        
        if (data.pages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = `
            <button class="pagination-btn" ${data.page === 1 ? 'disabled' : ''} onclick="app.goToPage(${data.page - 1})">←</button>
        `;

        for (let i = 1; i <= data.pages; i++) {
            if (i === 1 || i === data.pages || (i >= data.page - 2 && i <= data.page + 2)) {
                html += `<button class="pagination-btn ${i === data.page ? 'active' : ''}" onclick="app.goToPage(${i})">${i}</button>`;
            } else if (i === data.page - 3 || i === data.page + 3) {
                html += `<span class="pagination-ellipsis">...</span>`;
            }
        }

        html += `
            <button class="pagination-btn" ${data.page === data.pages ? 'disabled' : ''} onclick="app.goToPage(${data.page + 1})">→</button>
        `;

        container.innerHTML = html;
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadApplications();
    }

    toggleRejectedStageField(status) {
        const rejectedStageRow = document.getElementById('rejected-stage-row');
        if (status === 'rejected') {
            rejectedStageRow.style.display = 'grid';
        } else {
            rejectedStageRow.style.display = 'none';
            document.getElementById('rejected-at-stage').value = '';
        }
    }

    openApplicationModal(application = null) {
        const modal = document.getElementById('application-modal');
        const form = document.getElementById('application-form');
        const title = document.getElementById('modal-title');

        form.reset();
        document.getElementById('app-id').value = '';

        if (application) {
            title.textContent = 'Edit Application';
            document.getElementById('app-id').value = application.id;
            document.getElementById('company-name').value = application.company_name || '';
            document.getElementById('position-title').value = application.position_title || '';
            document.getElementById('app-status').value = application.status || 'applied';
            document.getElementById('applied-date').value = application.applied_date ? application.applied_date.split('T')[0] : '';
            document.getElementById('job-url').value = application.job_url || '';
            document.getElementById('location').value = application.location || '';
            document.getElementById('salary-min').value = application.salary_min || '';
            document.getElementById('salary-max').value = application.salary_max || '';
            document.getElementById('recruiter-name').value = application.recruiter_name || '';
            document.getElementById('recruiter-email').value = application.recruiter_email || '';
            document.getElementById('job-description').value = application.job_description || '';
            document.getElementById('notes').value = application.notes || '';
            document.getElementById('rejected-at-stage').value = application.rejected_at_stage || '';
            
            // Show/hide rejected stage field based on current status
            this.toggleRejectedStageField(application.status || 'applied');
        } else {
            title.textContent = 'Add Application';
            document.getElementById('applied-date').value = new Date().toISOString().split('T')[0];
            this.toggleRejectedStageField('applied');
        }

        modal.classList.add('active');
    }

    async editApplication(id) {
        try {
            const application = await api.getApplication(id);
            this.openApplicationModal(application);
        } catch (error) {
            this.showToast('Failed to load application', 'error');
        }
    }

    async handleApplicationSubmit(e) {
        e.preventDefault();

        const id = document.getElementById('app-id').value;
        const status = document.getElementById('app-status').value;
        const data = {
            company_name: document.getElementById('company-name').value,
            position_title: document.getElementById('position-title').value,
            status: status,
            applied_date: document.getElementById('applied-date').value || null,
            job_url: document.getElementById('job-url').value || null,
            location: document.getElementById('location').value || null,
            salary_min: parseFloat(document.getElementById('salary-min').value) || null,
            salary_max: parseFloat(document.getElementById('salary-max').value) || null,
            recruiter_name: document.getElementById('recruiter-name').value || null,
            recruiter_email: document.getElementById('recruiter-email').value || null,
            job_description: document.getElementById('job-description').value || null,
            notes: document.getElementById('notes').value || null,
            rejected_at_stage: status === 'rejected' ? (document.getElementById('rejected-at-stage').value || null) : null
        };

        try {
            if (id) {
                const result = await api.updateApplication(id, data);
                
                if (result.merged) {
                    this.showToast(`🔗 ${result.message}`, 'success');
                    // Show additional info about the merge
                    setTimeout(() => {
                        this.showToast(`ℹ️ Emails and reminders were transferred to the merged application`, 'info');
                    }, 1000);
                } else {
                    this.showToast('Application updated', 'success');
                }
            } else {
                await api.createApplication(data);
                this.showToast('Application created', 'success');
            }

            this.closeModals();
            this.loadApplications();
            
            if (this.currentView === 'dashboard') {
                this.loadDashboard();
            }
        } catch (error) {
            this.showToast('Failed to save application: ' + error.message, 'error');
        }
    }

    async fetchJobDescription() {
        const urlInput = document.getElementById('job-url');
        const descriptionTextarea = document.getElementById('job-description');
        const fetchBtn = document.getElementById('btn-fetch-description');
        const fetchText = fetchBtn.querySelector('.fetch-text');
        const fetchSpinner = fetchBtn.querySelector('.fetch-spinner');
        
        const url = urlInput.value.trim();
        
        if (!url) {
            this.showToast('Please enter a job URL first', 'warning');
            urlInput.focus();
            return;
        }
        
        // Show loading state
        fetchBtn.disabled = true;
        fetchText.style.display = 'none';
        fetchSpinner.style.display = 'block';
        
        try {
            const response = await fetch('/api/applications/scrape-job', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const result = await response.json();
            
            if (result.success) {
                descriptionTextarea.value = result.description;
                this.showToast('Job description fetched successfully!', 'success');
                
                // If title or company were detected and fields are empty, offer to fill them
                if (result.title && !document.getElementById('position-title').value) {
                    document.getElementById('position-title').value = result.title;
                }
                if (result.company && !document.getElementById('company-name').value) {
                    document.getElementById('company-name').value = result.company;
                }
            } else {
                this.showToast(result.error || 'Could not fetch job description', 'error');
            }
        } catch (error) {
            this.showToast('Failed to fetch job description: ' + error.message, 'error');
        } finally {
            // Reset button state
            fetchBtn.disabled = false;
            fetchText.style.display = 'inline';
            fetchSpinner.style.display = 'none';
        }
    }

    async deleteApplication(id) {
        if (!confirm('Are you sure you want to delete this application?')) {
            return;
        }

        try {
            await api.deleteApplication(id);
            this.showToast('Application deleted', 'success');
            this.loadApplications();
            
            if (this.currentView === 'dashboard') {
                this.loadDashboard();
            }
        } catch (error) {
            this.showToast('Failed to delete application', 'error');
        }
    }

    // ==========================================
    // Emails
    // ==========================================

    async loadEmails() {
        try {
            const data = await api.getUnprocessedEmails();
            this.renderEmails(data.emails);
            document.getElementById('unprocessed-count').textContent = data.count;
        } catch (error) {
            console.error('Failed to load emails:', error);
        }
    }

    renderEmails(emails) {
        const container = document.getElementById('email-list');
        
        if (!emails || emails.length === 0) {
            container.innerHTML = '<p class="empty-state">No unprocessed emails. Click "Scan Emails" to search your inbox.</p>';
            return;
        }

        container.innerHTML = emails.map(email => `
            <div class="email-item" data-id="${email.id}">
                <div class="email-content">
                    <div class="email-subject">${this.escapeHtml(email.subject)}</div>
                    <div class="email-sender">${this.escapeHtml(email.sender)} • ${this.formatDate(email.received_date)}</div>
                    <div class="email-detected">
                        ${email.detected_company ? `<span>Company: <strong>${this.escapeHtml(email.detected_company)}</strong></span>` : ''}
                        ${email.detected_position ? `<span>Position: <strong>${this.escapeHtml(email.detected_position)}</strong></span>` : ''}
                        <span class="confidence-badge ${email.confidence_score < 0.5 ? 'low' : ''}">${Math.round(email.confidence_score * 100)}% match</span>
                    </div>
                </div>
                <div class="email-actions">
                    <button class="btn-secondary btn-sm" onclick="app.createFromEmail(${email.id})">Create App</button>
                    <button class="btn-secondary btn-sm btn-danger" onclick="app.dismissEmail(${email.id})">Dismiss</button>
                </div>
            </div>
        `).join('');
    }

    async scanEmails() {
        const btn = document.getElementById('btn-scan-emails');
        btn.classList.add('loading');
        
        try {
            const result = await api.scanEmails({ days_back: 30, max_results: 100 });
            
            // Build detailed message
            let message = `Found ${result.new_emails} new job-related emails`;
            
            // Show skipped info if any
            const skipped = result.skipped || {};
            const totalSkipped = (skipped.dismissed || 0) + (skipped.already_processed || 0) + (skipped.pending || 0);
            
            if (totalSkipped > 0) {
                message += ` (${totalSkipped} skipped)`;
            }
            
            this.showToast(message, 'success');
            
            // Show additional info about dismissed emails
            if (skipped.dismissed > 0) {
                setTimeout(() => {
                    this.showToast(`ℹ️ ${skipped.dismissed} previously dismissed emails were skipped`, 'info');
                }, 1000);
            }
            
            this.loadEmails();
        } catch (error) {
            this.showToast('Failed to scan emails: ' + error.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    async autoProcessEmails() {
        const btn = document.getElementById('btn-auto-process');
        btn.classList.add('loading');
        
        try {
            const result = await api.autoProcessEmails({ min_confidence: 0.7 });
            
            // Build summary message
            let parts = [];
            if (result.created > 0) {
                parts.push(`${result.created} new`);
            }
            if (result.status_updated > 0) {
                parts.push(`${result.status_updated} updated`);
            }
            if (result.linked_to_existing > 0) {
                parts.push(`${result.linked_to_existing} linked`);
            }
            
            const message = parts.length > 0 
                ? `Processed: ${parts.join(', ')}` 
                : 'No emails to process';
            
            this.showToast(message, 'success');
            
            // Show status updates info
            if (result.status_updated > 0 && result.updates_info) {
                setTimeout(() => {
                    const updates = result.updates_info.slice(0, 3).map(u => u.change).join('; ');
                    this.showToast(`📈 Status updates: ${updates}`, 'info');
                }, 1000);
            }
            
            this.loadEmails();
            
            // Refresh dashboard if visible
            if (this.currentView === 'dashboard') {
                this.loadDashboard();
            }
        } catch (error) {
            this.showToast('Failed to auto-process: ' + error.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    async createFromEmail(emailId) {
        try {
            const result = await api.createApplicationFromEmail(emailId);
            
            if (result.duplicate) {
                if (result.status_updated) {
                    this.showToast(`✅ ${result.message}`, 'success');
                } else {
                    this.showToast(`ℹ️ ${result.message}`, 'info');
                }
            } else {
                this.showToast('Application created', 'success');
            }
            this.loadEmails();
            
            // Refresh dashboard if visible
            if (this.currentView === 'dashboard') {
                this.loadDashboard();
            }
        } catch (error) {
            this.showToast('Failed to create application', 'error');
        }
    }

    async dismissEmail(emailId) {
        try {
            await api.dismissEmail(emailId);
            this.loadEmails();
        } catch (error) {
            this.showToast('Failed to dismiss email', 'error');
        }
    }

    // ==========================================
    // Reminders
    // ==========================================

    async loadReminders() {
        try {
            const [due, upcoming] = await Promise.all([
                api.getDueReminders(),
                api.getReminders({ upcoming: 'true' })
            ]);
            
            this.renderDueReminders(due.reminders);
            this.renderUpcomingReminders(upcoming.reminders);
        } catch (error) {
            console.error('Failed to load reminders:', error);
        }
    }

    renderDueReminders(reminders) {
        const container = document.getElementById('due-reminders');
        
        if (!reminders || reminders.length === 0) {
            container.innerHTML = '<p class="empty-state">No reminders due today. Great job staying on top of things!</p>';
            return;
        }

        container.innerHTML = reminders.map(rem => {
            const isOverdue = new Date(rem.reminder_date) < new Date();
            return `
                <div class="reminder-item ${isOverdue ? 'overdue' : ''}" data-id="${rem.id}">
                    <div class="reminder-content">
                        <div class="reminder-company">${this.escapeHtml(rem.company_name || 'Unknown')}</div>
                        <div class="reminder-message">${this.escapeHtml(rem.message)}</div>
                        <div class="reminder-date">${this.formatDate(rem.reminder_date)}</div>
                    </div>
                    <div class="reminder-actions">
                        <button class="btn-secondary btn-sm" onclick="app.completeReminder(${rem.id})">✓ Done</button>
                        <button class="btn-secondary btn-sm" onclick="app.snoozeReminder(${rem.id})">⏰ +1 day</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderUpcomingReminders(reminders) {
        const container = document.getElementById('upcoming-reminders');
        const upcomingOnly = reminders.filter(r => new Date(r.reminder_date) > new Date());
        
        if (!upcomingOnly || upcomingOnly.length === 0) {
            container.innerHTML = '<p class="empty-state">No upcoming reminders.</p>';
            return;
        }

        container.innerHTML = upcomingOnly.slice(0, 10).map(rem => `
            <div class="reminder-item" data-id="${rem.id}">
                <div class="reminder-content">
                    <div class="reminder-company">${this.escapeHtml(rem.company_name || 'Unknown')}</div>
                    <div class="reminder-message">${this.escapeHtml(rem.message)}</div>
                    <div class="reminder-date">${this.formatDate(rem.reminder_date)}</div>
                </div>
                <div class="reminder-actions">
                    <button class="btn-secondary btn-sm btn-danger" onclick="app.dismissReminder(${rem.id})">✕</button>
                </div>
            </div>
        `).join('');
    }

    openReminderModal(applicationId) {
        const modal = document.getElementById('reminder-modal');
        document.getElementById('reminder-form').reset();
        document.getElementById('reminder-app-id').value = applicationId;
        
        // Default to 7 days from now
        const defaultDate = new Date();
        defaultDate.setDate(defaultDate.getDate() + 7);
        document.getElementById('reminder-date').value = defaultDate.toISOString().split('T')[0];
        
        modal.classList.add('active');
    }

    async handleReminderSubmit(e) {
        e.preventDefault();

        const data = {
            application_id: parseInt(document.getElementById('reminder-app-id').value),
            reminder_date: document.getElementById('reminder-date').value,
            message: document.getElementById('reminder-message').value || 'Follow up on application'
        };

        try {
            await api.createReminder(data);
            this.showToast('Reminder created', 'success');
            this.closeModals();
            
            if (this.currentView === 'reminders') {
                this.loadReminders();
            }
        } catch (error) {
            this.showToast('Failed to create reminder', 'error');
        }
    }

    async completeReminder(id) {
        try {
            await api.completeReminder(id);
            this.showToast('Reminder completed', 'success');
            this.loadReminders();
        } catch (error) {
            this.showToast('Failed to complete reminder', 'error');
        }
    }

    async snoozeReminder(id) {
        try {
            await api.snoozeReminder(id, 1);
            this.showToast('Reminder snoozed', 'info');
            this.loadReminders();
        } catch (error) {
            this.showToast('Failed to snooze reminder', 'error');
        }
    }

    async dismissReminder(id) {
        try {
            await api.dismissReminder(id);
            this.loadReminders();
        } catch (error) {
            this.showToast('Failed to dismiss reminder', 'error');
        }
    }

    async autoCreateReminders() {
        try {
            const result = await api.autoCreateReminders({ days_inactive: 7 });
            this.showToast(`Created ${result.created} follow-up reminders`, 'success');
            this.loadReminders();
        } catch (error) {
            this.showToast('Failed to create reminders', 'error');
        }
    }

    // ==========================================
    // Interview Management
    // ==========================================

    openInterviewModal(applicationId, interview = null) {
        const modal = document.getElementById('interview-modal');
        const form = document.getElementById('interview-form');
        const title = document.getElementById('interview-modal-title');
        
        form.reset();
        document.getElementById('interview-id').value = '';
        document.getElementById('interview-app-id').value = applicationId;
        document.getElementById('sync-to-calendar').checked = true;
        
        if (interview) {
            title.textContent = 'Edit Interview';
            document.getElementById('interview-id').value = interview.id;
            document.getElementById('interview-type').value = interview.interview_type || 'video_call';
            document.getElementById('interview-title').value = interview.title || '';
            
            if (interview.scheduled_at) {
                const dt = new Date(interview.scheduled_at);
                document.getElementById('interview-date').value = dt.toISOString().split('T')[0];
                document.getElementById('interview-time').value = dt.toTimeString().slice(0, 5);
            }
            
            document.getElementById('interview-duration').value = interview.duration_minutes || 60;
            document.getElementById('interview-meeting-link').value = interview.meeting_link || '';
            document.getElementById('interview-location').value = interview.location || '';
            document.getElementById('interviewer-name').value = interview.interviewer_name || '';
            document.getElementById('interviewer-email').value = interview.interviewer_email || '';
            document.getElementById('preparation-notes').value = interview.preparation_notes || '';
        } else {
            title.textContent = 'Schedule Interview';
            // Set default date to tomorrow
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            document.getElementById('interview-date').value = tomorrow.toISOString().split('T')[0];
            document.getElementById('interview-time').value = '10:00';
        }
        
        modal.classList.add('active');
    }

    async handleInterviewSubmit(e) {
        e.preventDefault();
        
        const btn = e.target.querySelector('button[type="submit"]');
        const btnText = btn.querySelector('.btn-text');
        const btnSpinner = btn.querySelector('.btn-spinner');
        
        const interviewId = document.getElementById('interview-id').value;
        const applicationId = document.getElementById('interview-app-id').value;
        
        const date = document.getElementById('interview-date').value;
        const time = document.getElementById('interview-time').value;
        const scheduledAt = new Date(`${date}T${time}`);
        
        const data = {
            application_id: parseInt(applicationId),
            interview_type: document.getElementById('interview-type').value,
            title: document.getElementById('interview-title').value || null,
            scheduled_at: scheduledAt.toISOString(),
            duration_minutes: parseInt(document.getElementById('interview-duration').value),
            meeting_link: document.getElementById('interview-meeting-link').value || null,
            location: document.getElementById('interview-location').value || null,
            interviewer_name: document.getElementById('interviewer-name').value || null,
            interviewer_email: document.getElementById('interviewer-email').value || null,
            preparation_notes: document.getElementById('preparation-notes').value || null,
            sync_to_calendar: document.getElementById('sync-to-calendar').checked
        };
        
        // Show loading state
        btn.disabled = true;
        btnText.style.display = 'none';
        btnSpinner.style.display = 'inline-block';
        
        try {
            let result;
            if (interviewId) {
                result = await api.updateInterview(interviewId, data);
                this.showToast('Interview updated', 'success');
            } else {
                result = await api.createInterview(data);
                
                if (result.calendar_synced) {
                    this.showToast('Interview scheduled and added to Google Calendar!', 'success');
                } else if (result.calendar_error) {
                    this.showToast(`Interview scheduled. Calendar sync failed: ${result.calendar_error}`, 'info');
                } else {
                    this.showToast('Interview scheduled', 'success');
                }
            }
            
            this.closeModals();
            this.loadApplications();
            
            if (this.currentView === 'dashboard') {
                this.loadDashboard();
            }
        } catch (error) {
            this.showToast('Failed to save interview: ' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btnText.style.display = 'inline';
            btnSpinner.style.display = 'none';
        }
    }

    openInterviewNotesModal(interview) {
        const modal = document.getElementById('interview-notes-modal');
        const form = document.getElementById('interview-notes-form');
        
        form.reset();
        this.switchNotesTab('general'); // Reset to first tab
        document.getElementById('notes-interview-id').value = interview.id;
        
        // Display interview info
        const infoDisplay = document.getElementById('interview-info-display');
        const interviewType = interview.interview_type ? interview.interview_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Interview';
        const dt = new Date(interview.scheduled_at);
        
        infoDisplay.innerHTML = `
            <h4>${this.escapeHtml(interview.company_name)} - ${this.escapeHtml(interview.position_title)}</h4>
            <p><strong>${interviewType}</strong></p>
            <p class="interview-datetime">${dt.toLocaleDateString()} at ${dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
            ${interview.interviewer_name ? `<p>Interviewer: ${this.escapeHtml(interview.interviewer_name)}</p>` : ''}
        `;
        
        // Show preparation notes if available
        const prepContainer = document.getElementById('prep-notes-container');
        const prepDisplay = document.getElementById('prep-notes-display');
        if (interview.preparation_notes) {
            prepDisplay.textContent = interview.preparation_notes;
            prepContainer.style.display = 'block';
        } else {
            prepContainer.style.display = 'none';
        }
        
        // Fill existing notes - General tab
        document.getElementById('post-interview-notes').value = interview.interview_notes || '';
        
        // Questions tab
        document.getElementById('questions-asked').value = interview.questions_asked || '';
        document.getElementById('your-questions').value = interview.your_questions || '';
        
        // Feedback tab
        document.getElementById('went-well').value = interview.went_well || '';
        document.getElementById('to-improve').value = interview.to_improve || '';
        document.getElementById('follow-up-items').value = interview.follow_up_items || '';
        
        // Outcome
        document.getElementById('interview-outcome').value = interview.outcome || '';
        document.getElementById('confidence-rating').value = interview.confidence_rating || '';
        document.getElementById('mark-completed').checked = interview.is_completed || false;
        
        modal.classList.add('active');
    }
    
    switchNotesTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.notes-tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabName}`);
        });
    }

    async handleInterviewNotesSubmit(e) {
        e.preventDefault();
        
        const interviewId = document.getElementById('notes-interview-id').value;
        
        const data = {
            // General notes
            interview_notes: document.getElementById('post-interview-notes').value || null,
            
            // Questions
            questions_asked: document.getElementById('questions-asked').value || null,
            your_questions: document.getElementById('your-questions').value || null,
            
            // Feedback
            went_well: document.getElementById('went-well').value || null,
            to_improve: document.getElementById('to-improve').value || null,
            follow_up_items: document.getElementById('follow-up-items').value || null,
            
            // Status
            outcome: document.getElementById('interview-outcome').value || null,
            confidence_rating: document.getElementById('confidence-rating').value || null,
            is_completed: document.getElementById('mark-completed').checked
        };
        
        try {
            await api.updateInterviewNotes(interviewId, data);
            this.showToast('Interview notes saved', 'success');
            this.closeModals();
            this.loadApplications();
            
            // Refresh detail modal if open
            const detailModal = document.getElementById('application-detail-modal');
            if (detailModal.classList.contains('active')) {
                const appId = detailModal.dataset.appId;
                if (appId) this.openApplicationDetail(parseInt(appId));
            }
        } catch (error) {
            this.showToast('Failed to save notes: ' + error.message, 'error');
        }
    }

    async cancelInterview(id) {
        if (!confirm('Are you sure you want to cancel this interview?')) {
            return;
        }
        
        try {
            await api.cancelInterview(id);
            this.showToast('Interview cancelled', 'info');
            this.loadApplications();
        } catch (error) {
            this.showToast('Failed to cancel interview: ' + error.message, 'error');
        }
    }

    async deleteInterview(id) {
        if (!confirm('Are you sure you want to delete this interview?')) {
            return;
        }
        
        try {
            await api.deleteInterview(id);
            this.showToast('Interview deleted', 'success');
            this.loadApplications();
            
            // Refresh detail modal if open
            const detailModal = document.getElementById('application-detail-modal');
            if (detailModal.classList.contains('active')) {
                const appId = detailModal.dataset.appId;
                if (appId) this.openApplicationDetail(parseInt(appId));
            }
        } catch (error) {
            this.showToast('Failed to delete interview: ' + error.message, 'error');
        }
    }

    // ==========================================
    // Application Detail View
    // ==========================================
    
    async openApplicationDetail(applicationId) {
        const modal = document.getElementById('application-detail-modal');
        modal.dataset.appId = applicationId;
        
        try {
            // Fetch application with details
            const application = await api.getApplication(applicationId);
            const interviewsData = await api.getInterviews({ application_id: applicationId });
            
            // Update header
            document.getElementById('detail-company-position').textContent = 
                `${application.company_name} - ${application.position_title}`;
            
            const statusBadge = document.getElementById('detail-status');
            statusBadge.textContent = this.formatStatus(application.status);
            statusBadge.className = `status-badge status-${application.status}`;
            
            // Meta info
            document.getElementById('detail-applied-date').textContent = 
                `Applied: ${this.formatDate(application.applied_date)}`;
            document.getElementById('detail-location').textContent = 
                application.location || '';
            
            // Links
            const linksContainer = document.getElementById('detail-links');
            let linksHtml = '';
            if (application.job_url && /^https?:\/\//i.test(application.job_url)) {
                linksHtml += `<a href="${this.escapeHtml(application.job_url)}" target="_blank" rel="noopener noreferrer">🔗 Job Posting</a>`;
            }
            linksContainer.innerHTML = linksHtml;
            
            // Interviews timeline
            this.renderInterviewTimeline(interviewsData.interviews || []);
            
            // Job description
            const jdContent = document.getElementById('detail-job-description');
            if (application.job_description) {
                jdContent.textContent = application.job_description;
                jdContent.classList.remove('empty-state');
            } else {
                jdContent.textContent = 'No job description saved.';
                jdContent.classList.add('empty-state');
            }
            
            // Notes
            const notesContainer = document.getElementById('detail-notes');
            if (application.notes) {
                notesContainer.innerHTML = `<div class="note-content">${this.escapeHtml(application.notes)}</div>`;
            } else {
                notesContainer.innerHTML = '<p class="empty-state">No notes.</p>';
            }
            
            modal.classList.add('active');
            
        } catch (error) {
            this.showToast('Failed to load application details', 'error');
        }
    }
    
    renderInterviewTimeline(interviews) {
        const container = document.getElementById('interview-timeline');

        if (!interviews || interviews.length === 0) {
            container.innerHTML = '<p class="empty-state">No interviews scheduled yet.</p>';
            return;
        }

        // Sort by date (upcoming first, then past)
        interviews.sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at));

        // Cache interview objects so onclick can reference them safely by ID
        interviews.forEach(iv => { this._interviewCache[iv.id] = iv; });

        container.innerHTML = interviews.map(interview => {
            const dt = new Date(interview.scheduled_at);
            const isPast = dt < new Date();
            const isToday = dt.toDateString() === new Date().toDateString();
            const interviewType = interview.interview_type ?
                interview.interview_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Interview';

            let statusClass = '';
            if (interview.is_cancelled) statusClass = 'cancelled';
            else if (interview.is_completed) statusClass = 'completed';

            let outcomeBadge = '';
            if (interview.outcome) {
                const safeOutcome = this.escapeHtml(interview.outcome);
                outcomeBadge = `<span class="interview-outcome-badge ${safeOutcome}">${safeOutcome}</span>`;
            }

            let notesPreview = '';
            if (interview.interview_notes) {
                const preview = interview.interview_notes.substring(0, 100);
                notesPreview = `<div class="interview-card-notes">${this.escapeHtml(preview)}${interview.interview_notes.length > 100 ? '...' : ''}</div>`;
            }

            const safeCalLink = interview.calendar_event_link ? this.escapeHtml(interview.calendar_event_link) : '';

            return `
                <div class="interview-card ${statusClass}">
                    <div class="interview-card-header">
                        <div>
                            <span class="interview-card-type">${this.escapeHtml(interviewType)}</span>
                            ${interview.title ? `<span class="interview-card-title"> - ${this.escapeHtml(interview.title)}</span>` : ''}
                            ${outcomeBadge}
                        </div>
                        <div class="interview-card-datetime">
                            ${isToday ? '<span class="interview-badge today">Today</span>' : ''}
                            ${dt.toLocaleDateString()} at ${dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </div>
                    </div>
                    ${interview.interviewer_name ? `<div class="interview-card-interviewer">With: ${this.escapeHtml(interview.interviewer_name)}</div>` : ''}
                    ${notesPreview}
                    <div class="interview-card-actions">
                        <button class="btn-small btn-secondary" onclick="app.openInterviewNotesModal(app._interviewCache[${parseInt(interview.id)}])">
                            ${isPast || interview.is_completed ? '📝 View/Edit Notes' : '📝 Add Notes'}
                        </button>
                        ${safeCalLink ? `<a href="${safeCalLink}" target="_blank" class="btn-small btn-secondary">📅 Calendar</a>` : ''}
                        ${!interview.is_cancelled ? `<button class="btn-small btn-secondary" onclick="app.cancelInterview(${parseInt(interview.id)})">Cancel</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    toggleSection(contentId) {
        const content = document.getElementById(contentId);
        const icon = content.previousElementSibling?.querySelector('.collapse-icon');
        
        content.classList.toggle('collapsed');
        
        if (icon) {
            icon.textContent = content.classList.contains('collapsed') ? '▼' : '▲';
        }
    }

    // ==========================================
    // Utilities
    // ==========================================

    closeModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = { success: '✓', error: '✕', info: 'ℹ' };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${this.escapeHtml(message)}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    formatStatus(status) {
        const labels = {
            applied: 'Applied',
            profile_viewed: 'Profile Viewed',
            phone_screen: 'Phone Screen',
            first_interview: '1st Interview',
            second_interview: '2nd Interview',
            third_interview: '3rd Interview',
            offer_received: 'Offer',
            offer_accepted: 'Accepted',
            offer_declined: 'Declined',
            rejected: 'Rejected',
            withdrawn: 'Withdrawn',
            no_response: 'No Response'
        };
        return labels[status] || status;
    }

    formatDate(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
        });
    }

    formatDateTime(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        // Show relative time for recent updates
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        // Show date for older updates
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Utility function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize app
const app = new JobTrackerApp();
