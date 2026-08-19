(() => {
    "use strict";

    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => Array.from(document.querySelectorAll(selector));
    const state = {
        items: new Map(),
        cursor: null,
        selectedId: null,
        controller: null,
        savedSearches: new Map(),
        loading: false,
    };

    const els = {
        form: $("#search-form"),
        query: $("#query-input"),
        station: $("#station-filter"),
        speaker: $("#speaker-filter"),
        from: $("#from-filter"),
        to: $("#to-filter"),
        audio: $("#audio-filter"),
        keyword: $("#keyword-filter"),
        caseStatus: $("#case-status-filter"),
        confidence: $("#confidence-filter"),
        confidenceOutput: $("#confidence-output"),
        fuzzy: $("#fuzzy-filter"),
        sort: $("#sort-filter"),
        status: $("#search-status"),
        list: $("#result-list"),
        summary: $("#result-summary"),
        timing: $("#result-timing"),
        activeFilters: $("#active-filters"),
        loadMore: $("#load-more-btn"),
        detailPanel: $("#detail-panel"),
        detailEmpty: $("#detail-empty"),
        detailContent: $("#detail-content"),
        savedSelect: $("#saved-search-select"),
        scopeBadge: $("#scope-badge"),
        toast: $("#toast"),
    };

    function toast(message, error = false) {
        els.toast.textContent = message;
        els.toast.classList.toggle("error", error);
        els.toast.classList.add("show");
        window.clearTimeout(toast.timer);
        toast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 3200);
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        if (response.status === 401) {
            window.location.href = "/";
            throw new Error("เซสชันหมดอายุ");
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        return data;
    }

    function selectedValues(select) {
        return Array.from(select.selectedOptions).map((option) => option.value).filter(Boolean);
    }

    function collectFilters() {
        const types = $$('input[name="message-type"]:checked').map((input) => input.value);
        const confidence = Number(els.confidence.value);
        return {
            q: els.query.value.trim(),
            fuzzy: els.fuzzy.checked,
            station_ids: selectedValues(els.station),
            speaker: els.speaker.value.trim(),
            from: els.from.value,
            to: els.to.value,
            message_types: types,
            has_audio: els.audio.value,
            keyword: els.keyword.value,
            case_status: els.caseStatus.value,
            min_confidence: confidence > 0 ? confidence : "",
            sort: els.sort.value,
        };
    }

    function filtersToParams(filters, includeLimit = true) {
        const params = new URLSearchParams();
        if (filters.q) params.set("q", filters.q);
        if (filters.fuzzy) params.set("fuzzy", "true");
        if (filters.station_ids.length) params.set("station_ids", filters.station_ids.join(","));
        if (filters.speaker) params.set("speaker", filters.speaker);
        if (filters.from) params.set("from", filters.from);
        if (filters.to) params.set("to", filters.to);
        if (filters.message_types.length && filters.message_types.length < 5) params.set("types", filters.message_types.join(","));
        if (filters.has_audio) params.set("has_audio", filters.has_audio);
        if (filters.keyword) params.set("keyword", filters.keyword);
        if (filters.case_status) params.set("case_status", filters.case_status);
        if (filters.min_confidence !== "") params.set("min_confidence", filters.min_confidence);
        if (filters.sort !== "latest") params.set("sort", filters.sort);
        if (includeLimit) params.set("limit", "50");
        return params;
    }

    function applyFilters(filters) {
        els.query.value = filters.q || "";
        els.fuzzy.checked = Boolean(filters.fuzzy === true || filters.fuzzy === "true");
        const stationIds = new Set((filters.station_ids || []).map(String));
        Array.from(els.station.options).forEach((option) => { option.selected = stationIds.has(option.value); });
        els.speaker.value = filters.speaker || "";
        els.from.value = filters.from || "";
        els.to.value = filters.to || "";
        els.audio.value = filters.has_audio === true ? "true" : filters.has_audio === false ? "false" : (filters.has_audio || "");
        els.keyword.value = filters.keyword || "";
        els.caseStatus.value = filters.case_status || "";
        els.confidence.value = filters.min_confidence || 0;
        els.fuzzy.checked = Boolean(filters.fuzzy === true || filters.fuzzy === "true");
        els.sort.value = filters.sort || "latest";
        const types = new Set(filters.message_types || ["voice_transcript", "alert", "text_chat", "tts", "ptt"]);
        $$('input[name="message-type"]').forEach((input) => { input.checked = types.has(input.value); });
        updateConfidenceLabel();
    }

    function filtersFromUrl() {
        const params = new URLSearchParams(window.location.search);
        return {
            q: params.get("q") || "",
            fuzzy: params.get("fuzzy") === "true",
            station_ids: (params.get("station_ids") || "").split(",").filter(Boolean),
            speaker: params.get("speaker") || "",
            from: params.get("from") || "",
            to: params.get("to") || "",
            message_types: (params.get("types") || "voice_transcript,alert,text_chat,tts,ptt").split(",").filter(Boolean),
            has_audio: params.get("has_audio") || "",
            keyword: params.get("keyword") || "",
            case_status: params.get("case_status") || "",
            min_confidence: params.get("min_confidence") || "",
            sort: params.get("sort") || "latest",
        };
    }

    function updateConfidenceLabel() {
        const value = Number(els.confidence.value);
        els.confidenceOutput.value = value === 0 ? "ไม่จำกัด" : value.toFixed(2);
        els.confidenceOutput.textContent = els.confidenceOutput.value;
    }

    function setStatus(title, detail = "", error = false) {
        els.status.replaceChildren();
        const strong = document.createElement("strong");
        strong.textContent = title;
        els.status.append(strong);
        if (detail) {
            const paragraph = document.createElement("p");
            paragraph.textContent = detail;
            els.status.append(paragraph);
        }
        els.status.style.display = "grid";
        els.status.style.borderColor = error ? "var(--danger)" : "";
    }

    function clearStatus() {
        els.status.style.display = "none";
    }

    function renderActiveFilters(filters) {
        els.activeFilters.replaceChildren();
        const labels = [];
        if (filters.q) labels.push(`ข้อความ: ${filters.q}`);
        if (filters.station_ids.length) labels.push(`สถานี ${filters.station_ids.length} แห่ง`);
        if (filters.speaker) labels.push(`ผู้พูด: ${filters.speaker}`);
        if (filters.from) labels.push(`ตั้งแต่: ${filters.from.replace("T", " ")}`);
        if (filters.to) labels.push(`ถึง: ${filters.to.replace("T", " ")}`);
        if (filters.keyword) labels.push(`Keyword: ${filters.keyword}`);
        if (filters.case_status) labels.push(`Incident: ${filters.case_status}`);
        if (filters.has_audio === "true") labels.push("มีเสียง");
        if (filters.has_audio === "false") labels.push("ไม่มีเสียง");
        if (filters.fuzzy) labels.push("คำใกล้เคียง");
        labels.forEach((label) => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = label;
            els.activeFilters.append(chip);
        });
    }

    const bangkokFormatter = new Intl.DateTimeFormat("th-TH", {
        timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });

    function formatTime(value) {
        try { return bangkokFormatter.format(new Date(value)); }
        catch { return value || "-"; }
    }

    function appendHighlightedText(container, text, query) {
        const raw = String(text || "");
        const needle = String(query || "").trim();
        if (!needle) {
            container.textContent = raw;
            return;
        }
        const index = raw.toLocaleLowerCase("th-TH").indexOf(needle.toLocaleLowerCase("th-TH"));
        if (index < 0) {
            container.textContent = raw;
            return;
        }
        container.append(document.createTextNode(raw.slice(0, index)));
        const mark = document.createElement("mark");
        mark.textContent = raw.slice(index, index + needle.length);
        container.append(mark, document.createTextNode(raw.slice(index + needle.length)));
    }

    function makeChip(label, kind = "") {
        const chip = document.createElement("span");
        chip.className = `chip ${kind}`.trim();
        chip.textContent = label;
        return chip;
    }

    function renderResult(item, query) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "result-item";
        button.dataset.id = item.id;
        if (item.id === state.selectedId) button.classList.add("selected");

        const meta = document.createElement("div");
        meta.className = "result-meta";
        const speaker = document.createElement("span");
        speaker.className = "result-speaker";
        speaker.textContent = item.speaker_name;
        const location = document.createElement("span");
        location.textContent = `${item.station_name || `Station ${item.station_id || "-"}`} / ${item.channel_name || (item.channel_id != null ? `ห้อง ${item.channel_id}` : "ไม่ระบุห้อง")}`;
        const time = document.createElement("time");
        time.dateTime = item.occurred_at;
        time.textContent = formatTime(item.occurred_at);
        meta.append(speaker, location, time);

        const message = document.createElement("div");
        message.className = "result-message";
        appendHighlightedText(message, item.display_text, query);

        const footer = document.createElement("div");
        footer.className = "result-footer";
        footer.append(makeChip(item.message_type));
        if (item.has_audio) footer.append(makeChip("มีเสียง", "audio"));
        (item.keywords || []).forEach((keyword) => footer.append(makeChip(keyword, "alert")));
        if (item.confidence != null) footer.append(makeChip(`confidence ${Number(item.confidence).toFixed(2)}`));
        if (item.bookmark_note || (item.bookmark_tags || []).length) footer.append(makeChip("bookmarked"));
        button.append(meta, message, footer);
        button.addEventListener("click", () => selectMessage(item.id));
        return button;
    }

    function renderResults(items, append, query) {
        if (!append) els.list.replaceChildren();
        const fragment = document.createDocumentFragment();
        items.forEach((item) => {
            state.items.set(item.id, item);
            fragment.append(renderResult(item, query));
        });
        els.list.append(fragment);
    }

    async function runSearch({ append = false } = {}) {
        const filters = collectFilters();
        const params = filtersToParams(filters);
        if (append && state.cursor) params.set("cursor", state.cursor);
        if (!append) {
            const urlQuery = filtersToParams(filters, false).toString();
            history.replaceState(null, "", `${window.location.pathname}${urlQuery ? `?${urlQuery}` : ""}`);
            state.cursor = null;
            state.items.clear();
            state.selectedId = null;
            els.detailPanel.classList.remove("open");
            els.detailEmpty.hidden = false;
            els.detailContent.hidden = true;
            $("#detail-audio").pause();
            renderActiveFilters(filters);
        }
        state.controller?.abort();
        const controller = new AbortController();
        state.controller = controller;
        state.loading = true;
        els.loadMore.disabled = true;
        if (!append) setStatus("กำลังค้นหา…", "ระบบกำลังอ่านข้อมูลจาก PostgreSQL");
        try {
            const data = await requestJson(`/api/chat/search?${params}`, { signal: controller.signal });
            renderResults(data.items, append, filters.q);
            state.cursor = data.next_cursor;
            els.loadMore.hidden = !data.has_more;
            els.summary.textContent = append
                ? `แสดงแล้ว ${state.items.size.toLocaleString("th-TH")} รายการ`
                : `พบ ${data.returned.toLocaleString("th-TH")} รายการในหน้านี้`;
            els.timing.textContent = `ใช้เวลา ${data.took_ms} ms`;
            if (state.items.size === 0) setStatus("ไม่พบข้อมูล", "ลองขยายช่วงเวลา ล้างบางตัวกรอง หรือปิดการค้นหาคำใกล้เคียง");
            else clearStatus();
        } catch (error) {
            if (error.name !== "AbortError") {
                setStatus("ค้นหาไม่สำเร็จ", error.message, true);
                toast(error.message, true);
            }
        } finally {
            if (state.controller === controller) {
                state.loading = false;
                els.loadMore.disabled = false;
            }
        }
    }

    function addMetadata(container, label, value) {
        const term = document.createElement("dt");
        term.textContent = label;
        const detail = document.createElement("dd");
        detail.textContent = value ?? "-";
        container.append(term, detail);
    }

    async function selectMessage(messageId) {
        const item = state.items.get(messageId);
        if (!item) return;
        state.selectedId = messageId;
        $$(".result-item").forEach((element) => element.classList.toggle("selected", Number(element.dataset.id) === messageId));
        els.detailEmpty.hidden = true;
        els.detailContent.hidden = false;
        els.detailPanel.classList.add("open");
        $("#detail-title").textContent = item.speaker_name;
        $("#detail-id").textContent = `#${item.id}`;
        const metadata = $("#detail-metadata");
        metadata.replaceChildren();
        addMetadata(metadata, "เวลา", formatTime(item.occurred_at));
        addMetadata(metadata, "สถานี", item.station_name || `Station ${item.station_id || "-"}`);
        addMetadata(metadata, "ห้อง", item.channel_name || item.channel_id || "ไม่ระบุ");
        addMetadata(metadata, "ประเภท", item.message_type);
        addMetadata(metadata, "Confidence", item.confidence == null ? "ไม่ระบุ" : Number(item.confidence).toFixed(2));
        if (item.audio_sha256) addMetadata(metadata, "SHA-256", item.audio_sha256);
        $("#detail-message").textContent = item.display_text;
        const keywords = $("#detail-keywords");
        keywords.replaceChildren();
        (item.keywords || []).forEach((keyword) => keywords.append(makeChip(keyword, "alert")));
        const audio = $("#detail-audio");
        audio.pause();
        audio.removeAttribute("src");
        audio.hidden = !item.has_audio;
        if (item.has_audio) audio.src = `/api/chat/messages/${item.id}/audio`;
        $("#bookmark-tags").value = (item.bookmark_tags || []).join(", ");
        $("#bookmark-note").value = item.bookmark_note || "";
        $("#correction-text").value = item.display_text || "";
        $("#correction-reason").value = "";
        $("#case-title").value = `${item.station_name || "สถานี"}: ${String(item.display_text || "").slice(0, 80)}`;
        $("#case-note").value = "";
        $("#context-list").replaceChildren();
        try {
            const context = await requestJson(`/api/chat/messages/${item.id}/context?before=10&after=10`);
            renderContext(context.items);
        } catch (error) {
            toast(`โหลดบริบทไม่สำเร็จ: ${error.message}`, true);
        }
    }

    function renderContext(items) {
        const container = $("#context-list");
        container.replaceChildren();
        items.forEach((item) => {
            const block = document.createElement("div");
            block.className = `context-item${item.selected ? " selected" : ""}`;
            const meta = document.createElement("div");
            meta.className = "context-meta";
            meta.textContent = `${formatTime(item.occurred_at)} · ${item.speaker_name}${item.has_audio ? " · มีเสียง" : ""}`;
            const text = document.createElement("div");
            text.className = "context-text";
            text.textContent = item.display_text;
            block.append(meta, text);
            container.append(block);
        });
    }

    async function bootstrap() {
        const data = await requestJson("/api/chat/bootstrap");
        const scope = data.scope || {};
        const isAdmin = scope.role === "admin";
        if (els.scopeBadge) {
            els.scopeBadge.textContent = isAdmin
                ? "ADMIN · ดูได้ทุกห้อง"
                : `USER · ${Number(scope.room_count || 0).toLocaleString("th-TH")} ห้องที่ได้รับอนุญาต`;
        }
        const stationHelp = $("#station-help");
        if (stationHelp) {
            stationHelp.textContent = isAdmin
                ? "Admin ค้นหาได้ทุกสถานีและทุกห้อง"
                : scope.room_count
                    ? "เลือกได้เฉพาะสถานีที่มีห้องได้รับอนุญาต"
                    : "ยังไม่มีห้องที่ได้รับอนุญาต กรุณาติดต่อ Admin";
        }
        els.station.replaceChildren();
        data.stations.forEach((station) => {
            const option = document.createElement("option");
            option.value = station.id;
            option.textContent = `${station.name} (#${station.id})`;
            els.station.append(option);
        });
        const speakerOptions = $("#speaker-options");
        speakerOptions.replaceChildren();
        data.speakers.forEach((speaker) => {
            const option = document.createElement("option");
            option.value = speaker.speaker_name;
            option.label = `${speaker.message_count} ข้อความ`;
            speakerOptions.append(option);
        });
        data.keywords.forEach((keyword) => {
            const option = document.createElement("option");
            option.value = keyword.keyword;
            option.textContent = `${keyword.keyword} (${keyword.hit_count})`;
            els.keyword.append(option);
        });
        state.savedSearches.clear();
        els.savedSelect.replaceChildren(new Option("ชุดค้นหาที่บันทึกไว้", ""));
        data.saved_searches.forEach((saved) => {
            state.savedSearches.set(String(saved.id), saved);
            els.savedSelect.add(new Option(saved.name, saved.id));
        });
        applyFilters(filtersFromUrl());
    }

    async function saveBookmark(event) {
        if (event.submitter?.value === "cancel") return;
        event.preventDefault();
        if (!state.selectedId) return;
        const data = await requestJson("/api/chat/bookmarks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message_id: state.selectedId,
                tags: $("#bookmark-tags").value.split(",").map((value) => value.trim()).filter(Boolean),
                note: $("#bookmark-note").value,
            }),
        });
        const item = state.items.get(state.selectedId);
        item.bookmark_tags = data.bookmark.tags;
        item.bookmark_note = data.bookmark.note;
        $("#bookmark-dialog").close();
        toast("บันทึก Bookmark แล้ว");
    }

    async function saveCorrection(event) {
        if (event.submitter?.value === "cancel") return;
        event.preventDefault();
        if (!state.selectedId) return;
        const data = await requestJson(`/api/chat/messages/${state.selectedId}/correction`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ corrected_text: $("#correction-text").value, reason: $("#correction-reason").value }),
        });
        const item = state.items.get(state.selectedId);
        item.content_corrected = data.corrected_text;
        item.display_text = data.corrected_text;
        $("#detail-message").textContent = data.corrected_text;
        $("#correction-dialog").close();
        toast(`บันทึก Revision ${data.revision_no} แล้ว`);
        runSearch();
    }

    async function saveCase(event) {
        if (event.submitter?.value === "cancel") return;
        event.preventDefault();
        if (!state.selectedId) return;
        const data = await requestJson("/api/chat/cases", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title: $("#case-title").value,
                severity: $("#case-severity").value,
                message_ids: [state.selectedId],
                note: $("#case-note").value,
            }),
        });
        $("#case-dialog").close();
        toast(`สร้าง Incident #${data.case.id} แล้ว`);
    }

    async function saveCurrentSearch(event) {
        if (event.submitter?.value === "cancel") return;
        event.preventDefault();
        const data = await requestJson("/api/chat/saved-searches", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: $("#saved-search-name").value,
                query: collectFilters(),
                notify_enabled: $("#saved-search-notify").checked,
            }),
        });
        state.savedSearches.set(String(data.saved_search.id), data.saved_search);
        const existing = Array.from(els.savedSelect.options).find((option) => option.value === String(data.saved_search.id));
        if (existing) existing.textContent = data.saved_search.name;
        else els.savedSelect.add(new Option(data.saved_search.name, data.saved_search.id));
        $("#saved-search-dialog").close();
        toast("บันทึกชุดค้นหาแล้ว");
    }

    function resetFilters() {
        applyFilters({});
        els.station.selectedIndex = -1;
        els.query.value = "";
        history.replaceState(null, "", window.location.pathname);
        runSearch();
    }

    function bindEvents() {
        els.form.addEventListener("submit", (event) => { event.preventDefault(); runSearch(); });
        $("#filter-search-btn").addEventListener("click", () => runSearch());
        $("#reset-btn").addEventListener("click", resetFilters);
        els.loadMore.addEventListener("click", () => runSearch({ append: true }));
        els.sort.addEventListener("change", () => runSearch());
        els.confidence.addEventListener("input", updateConfidenceLabel);
        $("#bookmark-btn").addEventListener("click", () => $("#bookmark-dialog").showModal());
        $("#correction-btn").addEventListener("click", () => $("#correction-dialog").showModal());
        $("#case-btn").addEventListener("click", () => $("#case-dialog").showModal());
        $("#detail-close-btn").addEventListener("click", () => els.detailPanel.classList.remove("open"));
        $("#save-search-btn").addEventListener("click", () => $("#saved-search-dialog").showModal());
        $("#help-btn").addEventListener("click", () => $("#help-dialog").showModal());
        $("#bookmark-dialog form").addEventListener("submit", (event) => saveBookmark(event).catch((error) => toast(`บันทึก Bookmark ไม่สำเร็จ: ${error.message}`, true)));
        $("#correction-dialog form").addEventListener("submit", (event) => saveCorrection(event).catch((error) => toast(`แก้ Transcript ไม่สำเร็จ: ${error.message}`, true)));
        $("#case-dialog form").addEventListener("submit", (event) => saveCase(event).catch((error) => toast(`สร้าง Incident ไม่สำเร็จ: ${error.message}`, true)));
        $("#saved-search-dialog form").addEventListener("submit", (event) => saveCurrentSearch(event).catch((error) => toast(`บันทึกชุดค้นหาไม่สำเร็จ: ${error.message}`, true)));
        els.savedSelect.addEventListener("change", () => {
            const saved = state.savedSearches.get(els.savedSelect.value);
            if (saved) { applyFilters(saved.query_json); runSearch(); }
        });
        $("#export-btn").addEventListener("click", () => {
            const params = filtersToParams(collectFilters(), false);
            window.location.href = `/api/chat/export.csv?${params}`;
        });
        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault(); els.query.focus(); els.query.select();
            }
            if (event.key === "Escape" && !$("dialog[open]")) els.detailPanel.classList.remove("open");
        });
    }

    async function init() {
        bindEvents();
        updateConfidenceLabel();
        try {
            await bootstrap();
            await runSearch();
        } catch (error) {
            setStatus("เปิดหน้าค้นหาไม่สำเร็จ", error.message, true);
            toast(error.message, true);
        }
    }

    init();
})();
