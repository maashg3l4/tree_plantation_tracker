document.addEventListener('alpine:init', () => {
    Alpine.data('healthAnalysis', (element) => ({
        element,
        open: false,
        loading: false,
        error: '',
        score: element.dataset.score ? Number(element.dataset.score) : null,
        confidence: Number(element.dataset.confidence || 0),
        issues: JSON.parse(element.dataset.issues || '[]'),
        recommendations: JSON.parse(element.dataset.recommendations || '[]'),
        createdAt: element.dataset.createdAt || '',

        get scoreBand() {
            if (this.score === null) return 'health-chip--empty';
            if (this.score >= 80) return 'health-chip--green';
            if (this.score >= 60) return 'health-chip--amber';
            if (this.score >= 40) return 'health-chip--orange';
            return 'health-chip--red';
        },

        get createdAtLabel() {
            if (!this.createdAt) return '';
            const created = new Date(this.createdAt);
            const elapsed = Math.max(0, Date.now() - created.getTime());
            const hours = Math.floor(elapsed / 3600000);
            const label = hours < 1 ? 'less than an hour ago' : hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
            return `Last analyzed ${label}`;
        },

        async analyze() {
            if (this.loading) return;
            this.loading = true;
            this.error = '';
            try {
                const response = await fetch(this.element.dataset.endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
                    },
                    body: new URLSearchParams({
                        csrfmiddlewaretoken: document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
                        force: this.score === null ? '0' : '1',
                    }),
                });
                const result = await response.json();
                if (!response.ok || !result.success) throw new Error(result.error || 'Could not analyze this tree image.');
                this.score = result.analysis.score;
                this.confidence = result.analysis.confidence;
                this.issues = result.analysis.issues;
                this.recommendations = result.analysis.recommendations;
                this.createdAt = result.analysis.created_at;
                this.element.dataset.score = String(this.score);
                this.element.dataset.confidence = String(this.confidence);
                this.element.dataset.issues = JSON.stringify(this.issues);
                this.element.dataset.recommendations = JSON.stringify(this.recommendations);
                this.element.dataset.createdAt = this.createdAt;
                this.element.querySelector('.health-chip span').textContent = `Health ${this.score}/100`;
                this.element.querySelector('.health-chip').className = `health-chip ${this.scoreBand}`;
            } catch (error) {
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },
    }));

    Alpine.data('impactReactions', (element) => ({
        element,
        counts: {},
        intensity: {},
        note: '',
        error: '',
        announcement: '',
        sending: false,
        helpOpen: false,
        helpType: 'water',
        helpMessage: '',
        queuedHelpIntensity: 1,
        pressTimer: null,
        tapTimer: null,
        lastTap: '',
        longPressed: '',

        init() {
            ['planted', 'inspiring', 'care', 'help', 'insight'].forEach((key) => {
                this.counts[key] = Number(this.element.dataset[`count${key[0].toUpperCase()}${key.slice(1)}`] || 0);
            });
            this.element.dataset.userReactions.split(',').filter(Boolean).forEach((entry) => {
                const [key, value] = entry.split(':');
                this.intensity[key] = Number(value);
            });
            this.applyPriorities();
        },

        applyPriorities() {
            let order = ['planted', 'inspiring', 'care', 'help', 'insight'];
            if (this.element.dataset.treeStatus === 'struggling') {
                order = ['care', 'help', 'inspiring', 'planted', 'insight'];
            } else if (this.element.dataset.treeStatus === 'thriving') {
                order = ['inspiring', 'planted', 'care', 'help', 'insight'];
            }
            if (this.element.dataset.hasHealthData === 'true') {
                order = ['insight', ...order.filter((key) => key !== 'insight')];
            }
            order.forEach((key, index) => {
                const button = this.element.querySelector(`[data-reaction-key="${key}"]`);
                if (button) button.style.order = String(index);
            });
        },

        startPress(key) {
            this.endPress();
            this.pressTimer = window.setTimeout(() => {
                this.pressTimer = null;
                this.longPressed = key;
                if (key === 'help') {
                    this.queuedHelpIntensity = 2;
                    this.helpOpen = true;
                } else {
                    this.sendReaction(key, 2);
                }
            }, 550);
        },

        endPress() {
            if (this.pressTimer !== null) {
                window.clearTimeout(this.pressTimer);
                this.pressTimer = null;
            }
        },

        tapReaction(key) {
            if (this.longPressed === key) {
                this.longPressed = '';
                return;
            }
            if (this.tapTimer && this.lastTap === key) {
                window.clearTimeout(this.tapTimer);
                this.tapTimer = null;
                this.lastTap = '';
                if (key === 'help') {
                    this.queuedHelpIntensity = 3;
                    this.helpOpen = true;
                    return;
                }
                this.sendReaction(key, 3);
                return;
            }
            if (this.tapTimer) window.clearTimeout(this.tapTimer);
            this.lastTap = key;
            if (key === 'help') {
                this.tapTimer = window.setTimeout(() => {
                    this.tapTimer = null;
                    this.lastTap = '';
                    this.queuedHelpIntensity = 1;
                    this.helpOpen = true;
                }, 320);
                return;
            }
            this.tapTimer = window.setTimeout(() => {
                this.tapTimer = null;
                this.lastTap = '';
                this.sendReaction(key, 1);
            }, 320);
        },

        submitHelp() {
            this.sendReaction('help', this.queuedHelpIntensity, {
                help_type: this.helpType,
                help_message: this.helpMessage,
            });
        },

        async sendReaction(key, level, extra = {}) {
            if (this.sending) return;
            this.sending = true;
            this.error = '';
            const payload = new URLSearchParams({
                form_type: 'react',
                tree_id: this.element.dataset.treeId,
                reaction_type: key,
                intensity: String(level),
                note: this.note,
                csrfmiddlewaretoken: this.element.querySelector('[name=csrfmiddlewaretoken]').value,
                ...extra,
            });
            try {
                const response = await fetch(this.element.dataset.endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
                    body: payload,
                });
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Could not save this reaction.');
                }
                this.counts = result.counts;
                this.intensity[key] = level;
                const button = this.element.querySelector(`[data-reaction-key="${key}"]`);
                button.dataset.intensity = String(level);
                button.classList.add('is-active');
                button.setAttribute('aria-pressed', 'true');
                this.element.querySelectorAll('[data-count-for]').forEach((count) => {
                    count.textContent = this.counts[count.dataset.countFor];
                });
                this.updateTimeline(result.timeline);
                this.announcement = `Saved ${button.getAttribute('aria-label')} at commitment level ${level}.`;
                this.helpOpen = false;
                this.helpMessage = '';
            } catch (error) {
                this.error = error.message;
            } finally {
                this.sending = false;
            }
        },

        updateTimeline(items) {
            const list = this.element.querySelector('[data-reaction-timeline]');
            if (!list) return;
            list.replaceChildren();
            if (!items.length) {
                const empty = document.createElement('li');
                empty.className = 'impact-timeline-empty';
                empty.textContent = 'Be the first to make an impact.';
                list.append(empty);
                return;
            }
            items.forEach((item) => {
                const row = document.createElement('li');
                const author = document.createElement('strong');
                author.textContent = `@${item.username}`;
                const note = document.createElement('span');
                note.textContent = `: ${item.reaction}${item.note ? ` — “${item.note}”` : ''}`;
                const time = document.createElement('time');
                time.dateTime = item.created_at;
                const seconds = Math.max(0, Math.floor((Date.now() - new Date(item.created_at).getTime()) / 1000));
                time.textContent = seconds < 60
                    ? 'just now'
                    : seconds < 3600
                        ? `${Math.floor(seconds / 60)}m ago`
                        : seconds < 86400
                            ? `${Math.floor(seconds / 3600)}h ago`
                            : `${Math.floor(seconds / 86400)}d ago`;
                row.append(author, note, time);
                list.append(row);
            });
        },
    }));
});

document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-delete-url]');
    if (!button || !window.confirm('Delete this tree post? This cannot be undone.')) return;
    const card = button.closest('.tree-card');
    const csrfToken = card.querySelector('[name=csrfmiddlewaretoken]')?.value;
    try {
        const response = await fetch(button.dataset.deleteUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || 'Could not delete this tree.');
        card.remove();
    } catch (error) {
        window.alert(error.message);
    }
});

document.body.addEventListener('htmx:afterRequest', (event) => {
    if (event.detail.successful && event.detail.elt.matches('.comment-form')) {
        event.detail.elt.reset();
    }
});
