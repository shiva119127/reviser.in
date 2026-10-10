// ==========================================================================
// YT REVISER — FRONTEND CONTROLLER & APPLICATION LOGIC
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    // ----------------------------------------------------------------------
    // CONFIGURATION & GLOBAL STATE
    // ----------------------------------------------------------------------
    let API_BASE_URL = (localStorage.getItem("ytReviserApiUrl") || "http://127.0.0.1:8000").replace(/\/+$/, "");

    let currentConversation = null;
    let currentResult = null;
    let activeJobPollInterval = null;
    let activeJobId = null;

    // ----------------------------------------------------------------------
    // DOM ELEMENT REFERENCES
    // ----------------------------------------------------------------------
    const serverStatusBadge = document.getElementById("serverStatusBadge");
    const themeButton = document.getElementById("themeButton");
    const settingsButton = document.getElementById("settingsButton");
    const settingsModal = document.getElementById("settingsModal");
    const closeSettings = document.getElementById("closeSettings");
    const apiUrlInput = document.getElementById("apiUrlInput");
    const saveApiBtn = document.getElementById("saveApiBtn");
    const modalThemeBtn = document.getElementById("modalThemeBtn");

    // Chat / Home
    const askForm = document.getElementById("askForm");
    const questionInput = document.getElementById("questionInput");
    const askButton = document.getElementById("askButton");
    const askLoading = document.getElementById("askLoading");
    const askError = document.getElementById("askError");
    const askErrorText = document.getElementById("askErrorText");
    const resultsContainer = document.getElementById("results");
    const answerBox = document.getElementById("answer");
    const sourcesList = document.getElementById("sourcesList");
    const followupsList = document.getElementById("followupsList");
    const bookmarkAnswerBtn = document.getElementById("bookmarkAnswer");
    const playlistFilterSelect = document.getElementById("playlistFilterSelect");

    // Ingest & Sync
    const ingestForm = document.getElementById("ingestForm");
    const ingestUrlInput = document.getElementById("ingestUrlInput");
    const btnIngest = document.getElementById("btnIngest");
    const btnSync = document.getElementById("btnSync");
    const jobPanel = document.getElementById("jobPanel");
    const jobStatusBadge = document.getElementById("jobStatusBadge");
    const jobTargetTitle = document.getElementById("jobTargetTitle");
    const jobStageSubtitle = document.getElementById("jobStageSubtitle");
    const jobRetryBtn = document.getElementById("jobRetryBtn");
    const metricTotal = document.getElementById("metricTotal");
    const metricCompleted = document.getElementById("metricCompleted");
    const metricSkipped = document.getElementById("metricSkipped");
    const metricFailed = document.getElementById("metricFailed");
    const progressBarFill = document.getElementById("progressBarFill");
    const jobVideosList = document.getElementById("jobVideosList");
    const recentJobsList = document.getElementById("recentJobsList");

    // Playlists, History, Bookmarks
    const playlistsGrid = document.getElementById("playlistsGrid");
    const refreshPlaylistsBtn = document.getElementById("refreshPlaylistsBtn");
    const historyList = document.getElementById("historyList");
    const clearHistoryBtn = document.getElementById("clearHistory");
    const bookmarkList = document.getElementById("bookmarkList");
    const clearBookmarksBtn = document.getElementById("clearBookmarks");

    // ----------------------------------------------------------------------
    // UTILITY FUNCTIONS
    // ----------------------------------------------------------------------
    function generateId() {
        return Date.now().toString(36) + "-" + Math.random().toString(36).substring(2, 9);
    }

    function showToast(message, duration = 3500) {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.textContent = message;
        toast.classList.remove("hidden");
        setTimeout(() => {
            toast.classList.add("hidden");
        }, duration);
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatMarkdown(text) {
        if (!text) return "<p>No answer provided.</p>";
        let escaped = escapeHtml(text);

        // Bold & Italics
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        escaped = escaped.replace(/\*(.*?)\*/g, "<em>$1</em>");
        escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");

        // Split by paragraphs
        const paragraphs = escaped.split(/\n\s*\n/);
        return paragraphs.map(p => {
            p = p.trim();
            if (p.startsWith("- ") || p.startsWith("* ")) {
                const items = p.split(/\n[-*]\s+/).filter(Boolean);
                return `<ul>${items.map(it => `<li>${it.replace(/^[-*]\s+/, "")}</li>`).join("")}</ul>`;
            }
            if (/^\d+\.\s+/.test(p)) {
                const items = p.split(/\n\d+\.\s+/).filter(Boolean);
                return `<ol>${items.map(it => `<li>${it.replace(/^\d+\.\s+/, "")}</li>`).join("")}</ol>`;
            }
            return `<p>${p.replace(/\n/g, "<br>")}</p>`;
        }).join("");
    }

    // ----------------------------------------------------------------------
    // NAVIGATION & TAB SWITCHING
    // ----------------------------------------------------------------------
    document.querySelectorAll(".nav").forEach(button => {
        button.addEventListener("click", () => {
            const pageId = button.dataset.page;
            showPage(pageId);
        });
    });

    function showPage(pageId) {
        document.querySelectorAll(".page").forEach(page => page.classList.remove("active"));
        document.querySelectorAll(".nav").forEach(nav => nav.classList.remove("active"));

        const targetPage = document.getElementById(pageId);
        if (targetPage) targetPage.classList.add("active");

        const targetNav = document.querySelector(`.nav[data-page="${pageId}"]`);
        if (targetNav) targetNav.classList.add("active");

        if (pageId === "playlistsPage") loadPlaylists();
        if (pageId === "historyPage") renderHistory();
        if (pageId === "bookmarksPage") renderBookmarks();

        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    // ----------------------------------------------------------------------
    // BACKEND HEALTH CHECK & STATUS
    // ----------------------------------------------------------------------
    async function checkBackendHealth() {
        try {
            const res = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
            if (res.ok) {
                const data = await res.json();
                serverStatusBadge.className = "server-status online";
                serverStatusBadge.querySelector(".status-text").textContent = `Online (${data.total_indexed_points} vectors)`;
                loadPlaylistDropdown();
                return true;
            }
        } catch (err) {
            // Check root as fallback
            try {
                const fallbackRes = await fetch(`${API_BASE_URL}/`, { method: "GET" });
                if (fallbackRes.ok) {
                    serverStatusBadge.className = "server-status online";
                    serverStatusBadge.querySelector(".status-text").textContent = "Backend Online";
                    return true;
                }
            } catch {}
        }
        serverStatusBadge.className = "server-status offline";
        serverStatusBadge.querySelector(".status-text").textContent = "Backend Offline";
        return false;
    }

    // Poll health periodically
    checkBackendHealth();
    setInterval(checkBackendHealth, 15000);

    // ----------------------------------------------------------------------
    // PLAYLIST DROPDOWN LOADER FOR CHAT FILTER
    // ----------------------------------------------------------------------
    async function loadPlaylistDropdown() {
        try {
            const res = await fetch(`${API_BASE_URL}/api/playlists`);
            if (res.ok) {
                const playlists = await res.json();
                if (playlistFilterSelect) {
                    const currentVal = playlistFilterSelect.value;
                    playlistFilterSelect.innerHTML = '<option value="">All Indexed Lectures</option>';
                    playlists.forEach(pl => {
                        const opt = document.createElement("option");
                        opt.value = pl.playlist_id;
                        opt.textContent = `${pl.title} (${pl.indexed_videos}/${pl.total_videos} videos)`;
                        playlistFilterSelect.appendChild(opt);
                    });
                    playlistFilterSelect.value = currentVal;
                }
            }
        } catch (e) {}
    }

    // ----------------------------------------------------------------------
    // CHAT & QUESTION ANSWERING
    // ----------------------------------------------------------------------
    askForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const question = questionInput.value.trim();
        if (!question) return;

        const selectedPlaylist = playlistFilterSelect ? playlistFilterSelect.value : null;
        await submitQuestion(question, selectedPlaylist);
    });

    async function submitQuestion(question, playlistId = null) {
        askError.classList.add("hidden");
        resultsContainer.classList.add("hidden");
        askLoading.classList.remove("hidden");
        askButton.disabled = true;

        try {
            const payload = {
                question: question,
                playlist_id: playlistId || null,
                top_k: 5
            };

            const response = await fetch(`${API_BASE_URL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Server returned status ${response.status}`);
            }

            const data = await response.json();
            currentResult = { question, ...data };
            
            saveToHistory(question, data);
            renderAnswer(data);
        } catch (err) {
            console.error("Chat error:", err);
            askErrorText.textContent = `Error: ${err.message}. Please verify the backend is running.`;
            askError.classList.remove("hidden");
        } finally {
            askLoading.classList.add("hidden");
            askButton.disabled = false;
        }
    }

    function renderAnswer(data) {
        resultsContainer.classList.remove("hidden");

        // Format Answer
        answerBox.innerHTML = formatMarkdown(data.answer);

        // Render Sources with clickable timestamps
        sourcesList.innerHTML = "";
        const sources = data.sources || [];
        if (sources.length === 0) {
            sourcesList.innerHTML = '<p class="empty-state-text">No specific lecture sources matched this query.</p>';
        } else {
            sources.forEach(src => {
                const mins = Math.floor(src.start / 60);
                const secs = Math.floor(src.start % 60);
                const timeLabel = `${mins}:${secs.toString().padStart(2, "0")}`;

                const item = document.createElement("div");
                item.className = "source-item";
                item.innerHTML = `
                    <div class="source-top-row">
                        <span class="source-title">${escapeHtml(src.title)}</span>
                        <a href="${escapeHtml(src.timestamped_url)}" target="_blank" rel="noopener noreferrer" class="source-link-btn">
                            ▷ Jump to ${timeLabel}
                        </a>
                    </div>
                    ${src.text ? `<div class="source-excerpt">"${escapeHtml(src.text.substring(0, 240))}..."</div>` : ""}
                `;
                sourcesList.appendChild(item);
            });
        }

        // Render Follow-up Questions
        followupsList.innerHTML = "";
        const followups = data.follow_up_questions || [];
        if (followups.length > 0) {
            document.getElementById("followupCard").classList.remove("hidden");
            followups.forEach(q => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "followup-btn";
                btn.innerHTML = `<span>✦</span> <span>${escapeHtml(q)}</span>`;
                btn.addEventListener("click", () => {
                    questionInput.value = q;
                    submitQuestion(q, playlistFilterSelect ? playlistFilterSelect.value : null);
                });
                followupsList.appendChild(btn);
            });
        } else {
            document.getElementById("followupCard").classList.add("hidden");
        }

        updateBookmarkButtonState();
        resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // ----------------------------------------------------------------------
    // INGESTION & PLAYLIST SYNCHRONIZATION
    // ----------------------------------------------------------------------
    ingestForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = ingestUrlInput.value.trim();
        if (!url) return;
        await startIngestion(url, false);
    });

    btnSync.addEventListener("click", async () => {
        const url = ingestUrlInput.value.trim();
        if (!url) {
            alert("Please enter a YouTube playlist URL to synchronize.");
            return;
        }
        await startIngestion(url, false);
    });

    async function startIngestion(url, forceReprocess = false) {
        btnIngest.disabled = true;
        btnSync.disabled = true;

        try {
            const res = await fetch(`${API_BASE_URL}/api/ingest`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url: url, force_reprocess: forceReprocess })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Ingestion initiation failed: ${res.status}`);
            }

            const jobData = await res.json();
            activeJobId = jobData.job_id;
            showToast(`Ingestion started: ${jobData.job_id}`);
            
            jobPanel.classList.remove("hidden");
            renderJobStatus(jobData);
            startJobPolling(activeJobId);
        } catch (err) {
            alert(`Could not start ingestion: ${err.message}`);
        } finally {
            btnIngest.disabled = false;
            btnSync.disabled = false;
        }
    }

    function startJobPolling(jobId) {
        if (activeJobPollInterval) clearInterval(activeJobPollInterval);

        activeJobPollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/api/ingest/${jobId}`);
                if (!res.ok) return;

                const job = await res.json();
                renderJobStatus(job);

                if (job.status === "completed" || job.status === "partially_completed" || job.status === "failed") {
                    clearInterval(activeJobPollInterval);
                    activeJobPollInterval = null;
                    checkBackendHealth();
                    loadRecentJobs();
                    loadPlaylistDropdown();

                    if (job.skipped_videos === job.total_videos && job.total_videos > 0) {
                        showToast("Your playlist is already up to date.");
                    } else if (job.status === "completed") {
                        showToast("Ingestion completed successfully!");
                    }
                }
            } catch (err) {
                console.warn("Polling error:", err);
            }
        }, 1200);
    }

    function renderJobStatus(job) {
        jobStatusBadge.textContent = job.status.toUpperCase();
        jobStatusBadge.className = `job-status-badge ${job.status}`;

        jobTargetTitle.textContent = job.playlist_title || (job.is_playlist ? "YouTube Playlist" : "YouTube Video");
        
        let stageText = `Current Stage: ${job.current_stage}`;
        if (job.current_video_title) {
            stageText += ` · ${job.current_video_title}`;
        }
        jobStageSubtitle.textContent = stageText;

        metricTotal.textContent = job.total_videos;
        metricCompleted.textContent = job.completed_videos;
        metricSkipped.textContent = job.skipped_videos;
        metricFailed.textContent = job.failed_videos;

        const totalProcessed = job.completed_videos + job.skipped_videos + job.failed_videos;
        const percent = job.total_videos > 0 ? Math.round((totalProcessed / job.total_videos) * 100) : 0;
        progressBarFill.style.width = `${percent}%`;

        // Render video items list
        jobVideosList.innerHTML = "";
        (job.videos || []).forEach(v => {
            const row = document.createElement("div");
            row.className = "job-video-item";
            const badgeClass = v.status === "failed" ? "danger" : v.status === "completed" ? "success" : "";
            const errTooltip = v.error ? `title="${escapeHtml(v.error)}"` : "";
            row.innerHTML = `
                <span>${escapeHtml(v.title)}</span>
                <span class="job-video-stage ${badgeClass}" ${errTooltip}>
                    ${escapeHtml(v.stage)}${v.error ? ' ⚠️' : ''}
                </span>
            `;
            jobVideosList.appendChild(row);
        });

        if (job.failed_videos > 0) {
            jobRetryBtn.classList.remove("hidden");
            jobRetryBtn.textContent = `↻ Retry Failed Items (${job.failed_videos})`;
            jobRetryBtn.onclick = async () => {
                try {
                    const res = await fetch(`${API_BASE_URL}/api/ingest/${job.job_id}/retry`, { method: "POST" });
                    if (res.ok) {
                        const newJob = await res.json();
                        activeJobId = newJob.job_id;
                        startJobPolling(activeJobId);
                        showToast("Retrying failed playlist items...");
                    }
                } catch (e) {
                    alert(`Retry failed: ${e.message}`);
                }
            };
        } else {
            jobRetryBtn.classList.add("hidden");
        }
    }

    async function loadRecentJobs() {
        try {
            const res = await fetch(`${API_BASE_URL}/api/ingest`);
            if (res.ok) {
                const jobs = await res.json();
                if (jobs.length === 0) {
                    recentJobsList.innerHTML = '<p class="empty-state-text">No ingestion jobs run yet.</p>';
                    return;
                }
                recentJobsList.innerHTML = "";
                jobs.slice(0, 5).forEach(j => {
                    const el = document.createElement("div");
                    el.className = "job-video-item";
                    el.innerHTML = `
                        <div>
                            <b>${escapeHtml(j.playlist_title || j.url)}</b>
                            <small style="display:block; color:var(--text-muted);">${j.job_id} · ${j.completed_videos}/${j.total_videos} completed</small>
                        </div>
                        <span class="job-video-stage">${j.status}</span>
                    `;
                    recentJobsList.appendChild(el);
                });
            }
        } catch (e) {}
    }

    // ----------------------------------------------------------------------
    // PLAYLISTS PAGE
    // ----------------------------------------------------------------------
    async function loadPlaylists() {
        playlistsGrid.innerHTML = '<p class="empty-state-text">Loading registered playlists...</p>';
        try {
            const res = await fetch(`${API_BASE_URL}/api/playlists`);
            if (res.ok) {
                const playlists = await res.json();
                if (playlists.length === 0) {
                    playlistsGrid.innerHTML = '<p class="empty-state-text">No playlists indexed yet. Use the "Ingest & Sync" tab to add one.</p>';
                    return;
                }
                playlistsGrid.innerHTML = "";
                playlists.forEach(pl => {
                    const card = document.createElement("div");
                    card.className = "playlist-card";
                    card.innerHTML = `
                        <div>
                            <h3>${escapeHtml(pl.title)}</h3>
                            <div class="playlist-meta">
                                <div>Indexed: ${pl.indexed_videos} / ${pl.total_videos} videos</div>
                                <div>ID: <code>${escapeHtml(pl.playlist_id)}</code></div>
                            </div>
                        </div>
                        <button class="primary-btn sync-pl-btn" data-id="${escapeHtml(pl.playlist_id)}">
                            ⟳ Sync Playlist
                        </button>
                    `;
                    card.querySelector(".sync-pl-btn").addEventListener("click", async () => {
                        try {
                            const syncRes = await fetch(`${API_BASE_URL}/api/playlists/${pl.playlist_id}/sync`, { method: "POST" });
                            if (syncRes.ok) {
                                const job = await syncRes.json();
                                showPage("ingestPage");
                                jobPanel.classList.remove("hidden");
                                activeJobId = job.job_id;
                                renderJobStatus(job);
                                startJobPolling(activeJobId);
                            }
                        } catch (err) {
                            alert(`Failed to sync playlist: ${err.message}`);
                        }
                    });
                    playlistsGrid.appendChild(card);
                });
            }
        } catch (err) {
            playlistsGrid.innerHTML = `<p class="empty-state-text">Could not load playlists: ${err.message}</p>`;
        }
    }

    refreshPlaylistsBtn.addEventListener("click", loadPlaylists);

    // ----------------------------------------------------------------------
    // HISTORY & BOOKMARKS MANAGEMENT
    // ----------------------------------------------------------------------
    function getHistory() {
        try {
            return JSON.parse(localStorage.getItem("ytReviserHistory")) || [];
        } catch { return []; }
    }

    function saveToHistory(question, data) {
        const history = getHistory();
        history.unshift({
            id: generateId(),
            question,
            answer: data.answer,
            sources: data.sources || [],
            follow_up_questions: data.follow_up_questions || [],
            timestamp: new Date().toISOString()
        });
        localStorage.setItem("ytReviserHistory", JSON.stringify(history.slice(0, 50)));
    }

    function renderHistory() {
        const history = getHistory();
        historyList.innerHTML = "";
        if (history.length === 0) {
            historyList.innerHTML = '<p class="empty-state-text">No conversation history saved yet.</p>';
            return;
        }
        history.forEach(item => {
            const div = document.createElement("div");
            div.className = "history-item";
            div.innerHTML = `
                <div class="item-main">
                    <h4>${escapeHtml(item.question)}</h4>
                    <small>${new Date(item.timestamp).toLocaleString()}</small>
                </div>
                <button class="secondary-btn btn-view-history">View</button>
            `;
            div.querySelector(".btn-view-history").addEventListener("click", () => {
                showPage("homePage");
                questionInput.value = item.question;
                renderAnswer(item);
            });
            historyList.appendChild(div);
        });
    }

    clearHistoryBtn.addEventListener("click", () => {
        if (confirm("Clear all search history?")) {
            localStorage.removeItem("ytReviserHistory");
            renderHistory();
        }
    });

    function getBookmarks() {
        try {
            return JSON.parse(localStorage.getItem("ytReviserBookmarks")) || [];
        } catch { return []; }
    }

    function isCurrentBookmarked() {
        if (!currentResult) return false;
        const bms = getBookmarks();
        return bms.some(b => b.question === currentResult.question);
    }

    function updateBookmarkButtonState() {
        if (isCurrentBookmarked()) {
            bookmarkAnswerBtn.classList.add("saved");
            bookmarkAnswerBtn.textContent = "♥ Saved";
        } else {
            bookmarkAnswerBtn.classList.remove("saved");
            bookmarkAnswerBtn.textContent = "♡ Save";
        }
    }

    bookmarkAnswerBtn.addEventListener("click", () => {
        if (!currentResult) return;
        const bms = getBookmarks();
        const existingIdx = bms.findIndex(b => b.question === currentResult.question);
        if (existingIdx !== -1) {
            bms.splice(existingIdx, 1);
            showToast("Bookmark removed");
        } else {
            bms.unshift({
                id: generateId(),
                question: currentResult.question,
                answer: currentResult.answer,
                sources: currentResult.sources || [],
                savedAt: new Date().toISOString()
            });
            showToast("Bookmark saved");
        }
        localStorage.setItem("ytReviserBookmarks", JSON.stringify(bms));
        updateBookmarkButtonState();
    });

    function renderBookmarks() {
        const bookmarks = getBookmarks();
        bookmarkList.innerHTML = "";
        if (bookmarks.length === 0) {
            bookmarkList.innerHTML = '<p class="empty-state-text">No bookmarks saved yet. Click "♡ Save" on any revision explanation.</p>';
            return;
        }
        bookmarks.forEach(bm => {
            const div = document.createElement("div");
            div.className = "bookmark-item";
            div.innerHTML = `
                <div class="item-main">
                    <h4>${escapeHtml(bm.question)}</h4>
                    <small>Saved ${new Date(bm.savedAt).toLocaleDateString()}</small>
                </div>
                <div style="display:flex; gap:8px;">
                    <button class="secondary-btn btn-view-bm">Open</button>
                    <button class="danger-btn btn-del-bm">Delete</button>
                </div>
            `;
            div.querySelector(".btn-view-bm").addEventListener("click", () => {
                showPage("homePage");
                questionInput.value = bm.question;
                renderAnswer(bm);
            });
            div.querySelector(".btn-del-bm").addEventListener("click", () => {
                const updated = getBookmarks().filter(b => b.id !== bm.id);
                localStorage.setItem("ytReviserBookmarks", JSON.stringify(updated));
                renderBookmarks();
                updateBookmarkButtonState();
            });
            bookmarkList.appendChild(div);
        });
    }

    clearBookmarksBtn.addEventListener("click", () => {
        if (confirm("Clear all bookmarks?")) {
            localStorage.removeItem("ytReviserBookmarks");
            renderBookmarks();
            updateBookmarkButtonState();
        }
    });

    // ----------------------------------------------------------------------
    // SETTINGS & THEME TOGGLE
    // ----------------------------------------------------------------------
    function toggleTheme() {
        document.body.classList.toggle("light");
        const isLight = document.body.classList.contains("light");
        localStorage.setItem("ytReviserTheme", isLight ? "light" : "dark");
        themeButton.textContent = isLight ? "☀ Light Mode" : "☾ Dark Mode";
        modalThemeBtn.textContent = isLight ? "☀ Light Mode" : "☾ Dark Mode";
    }

    if (localStorage.getItem("ytReviserTheme") === "light") {
        document.body.classList.add("light");
        themeButton.textContent = "☀ Light Mode";
        modalThemeBtn.textContent = "☀ Light Mode";
    }

    themeButton.addEventListener("click", toggleTheme);
    modalThemeBtn.addEventListener("click", toggleTheme);

    settingsButton.addEventListener("click", () => {
        apiUrlInput.value = API_BASE_URL;
        settingsModal.classList.remove("hidden");
    });

    closeSettings.addEventListener("click", () => settingsModal.classList.add("hidden"));
    settingsModal.addEventListener("click", (e) => {
        if (e.target === settingsModal) settingsModal.classList.add("hidden");
    });

    saveApiBtn.addEventListener("click", () => {
        const url = apiUrlInput.value.trim().replace(/\/+$/, "");
        if (url) {
            API_BASE_URL = url;
            localStorage.setItem("ytReviserApiUrl", url);
            showToast("Backend API URL updated.");
            settingsModal.classList.add("hidden");
            checkBackendHealth();
        }
    });

    // Initial setup
    loadRecentJobs();
});
