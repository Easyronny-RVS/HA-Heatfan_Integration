/*
 * Heatfan-kaart: per modus een temperatuurbereik en een snelheidsbereik met
 * twee dubbele schuifregelaars, zoals in de Heatfan-app. Onofficieel.
 * Gebruik in een dashboard:   type: custom:heatfan-card
 * Optioneel:                  controller: 140808D87208   en   title: Mijn titel
 */

const HEATFAN_TEXT = {
  nl: {
    title: "Heatfan",
    mode: "Modus",
    temperature: "Temperatuur",
    speed: "Snelheid",
    save: "Opslaan",
    saved: "Opgeslagen",
    undo: "Ongedaan maken",
    activate: "Activeer modus",
    active: "Actieve modus",
    unsaved: "Niet-opgeslagen wijzigingen",
    none: "Geen Heatfan-controller gevonden. Controleer of de integratie is geladen.",
    controller: "Controller",
    error: "Opslaan mislukt",
  },
  en: {
    title: "Heatfan",
    mode: "Mode",
    temperature: "Temperature",
    speed: "Speed",
    save: "Save",
    saved: "Saved",
    undo: "Undo",
    activate: "Activate mode",
    active: "Active mode",
    unsaved: "Unsaved changes",
    none: "No Heatfan controller found. Check that the integration is loaded.",
    controller: "Controller",
    error: "Saving failed",
  },
};

const HEATFAN_RANGES = {
  temp: { lo: "start-temp", hi: "max-temp", min: 1, max: 100, unit: "\u00b0C", color: "#5fcf45", tint: "#e9f7e5" },
  speed: { lo: "start-speed", hi: "max-speed", min: 1, max: 10, unit: "", color: "#6b5cff", tint: "#e6e3ff" },
};
const HEATFAN_THUMB = 22;

class HeatfanCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._draft = {};
    this._dirty = {};
    this._mode = null;
    this._ctrl = null;
    this._config = {};
    this._built = false;
    this._msgTimer = null;
  }

  setConfig(config) {
    this._config = config || {};
    if (this._config.controller) this._ctrl = String(this._config.controller);
  }

  getCardSize() {
    return 7;
  }

  static getStubConfig() {
    return {};
  }

  set hass(hass) {
    this._hass = hass;
    this._sync();
  }

  // ---------- hulpfuncties ----------
  get _t() {
    const lang = String((this._hass && ((this._hass.locale && this._hass.locale.language) || this._hass.language)) || "en").slice(0, 2);
    return HEATFAN_TEXT[lang] || HEATFAN_TEXT.en;
  }

  _key() {
    return this._ctrl + ":" + this._mode;
  }

  _discover() {
    const found = {};
    const states = (this._hass && this._hass.states) || {};
    for (const eid of Object.keys(states)) {
      const a = states[eid].attributes;
      if (!a || !a.heatfan_controller) continue;
      const id = String(a.heatfan_controller);
      if (!found[id]) found[id] = { id: id, room: null, numbers: {}, select: null };
      const c = found[id];
      if (a.heatfan_room) c.room = a.heatfan_room;
      if (eid.indexOf("number.") === 0 && a.heatfan_mode && a.heatfan_field) {
        if (!c.numbers[a.heatfan_mode]) c.numbers[a.heatfan_mode] = {};
        c.numbers[a.heatfan_mode][a.heatfan_field] = eid;
      } else if (eid.indexOf("select.") === 0) {
        c.select = eid;
      }
    }
    return found;
  }

  _activeMode(c) {
    if (!c || !c.select) return null;
    const st = this._hass.states[c.select];
    const n = st ? parseInt(st.state, 10) : NaN;
    return n >= 1 && n <= 6 ? n : null;
  }

  _readFromStates(c, mode) {
    const out = {};
    const fields = c.numbers[mode] || {};
    for (const kind of Object.keys(HEATFAN_RANGES)) {
      for (const f of [HEATFAN_RANGES[kind].lo, HEATFAN_RANGES[kind].hi]) {
        const st = fields[f] ? this._hass.states[fields[f]] : null;
        const v = st ? parseFloat(st.state) : NaN;
        out[f] = Number.isFinite(v) ? Math.round(v) : null;
      }
    }
    return out;
  }

  _complete(d) {
    return d && Object.keys(d).every((k) => d[k] !== null);
  }

  // ---------- opbouw ----------
  _build() {
    const r = this.shadowRoot;
    r.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { display: block; padding: 16px; box-sizing: border-box; }
        .head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
        .title { font-size: 20px; font-weight: 600; color: var(--primary-text-color, #212121); }
        select.ctrl { font: inherit; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121); }
        .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
        .tab { position: relative; cursor: pointer; border: 2px solid var(--divider-color, #ccc); background: transparent;
          color: var(--primary-text-color, #212121); border-radius: 999px; padding: 6px 14px; font: inherit; font-weight: 600; }
        .tab.sel { border-color: #cc0000; color: #cc0000; }
        .tab .dot { position: absolute; top: -3px; right: -3px; width: 11px; height: 11px; border-radius: 50%;
          background: #2ea043; border: 2px solid var(--card-background-color, #fff); display: none; }
        .tab.act .dot { display: block; }
        .section { margin-bottom: 18px; }
        .label { font-weight: 600; margin-bottom: 8px; color: var(--primary-text-color, #212121); }
        .row { display: grid; grid-template-columns: 60px 1fr 60px; gap: 10px; align-items: center; }
        .limits { display: grid; grid-template-columns: 60px 1fr 60px; gap: 10px; margin-top: 4px;
          font-size: 13px; color: var(--secondary-text-color, #727272); }
        .limits span:first-child { text-align: left; } .limits span:last-child { text-align: right; }
        .num { width: 60px; height: 44px; box-sizing: border-box; border: 3px solid var(--c); border-radius: 12px; text-align: center;
          font: inherit; font-weight: 700; background: transparent; color: var(--primary-text-color, #212121);
          -moz-appearance: textfield; appearance: textfield; padding: 0; }
        .num::-webkit-outer-spin-button, .num::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
        .dual { position: relative; height: 44px; }
        .track { position: absolute; left: 0; right: 0; top: 4px; bottom: 4px; border-radius: 6px; background: var(--tint); }
        .fill { position: absolute; top: 4px; bottom: 4px; background: var(--c); }
        input[type=range] { position: absolute; left: 0; top: 0; width: 100%; height: 44px; margin: 0; background: transparent;
          -webkit-appearance: none; appearance: none; pointer-events: none; outline: none; }
        input[type=range]::-webkit-slider-runnable-track { background: transparent; height: 44px; border: none; }
        input[type=range]::-moz-range-track { background: transparent; height: 44px; border: none; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; pointer-events: auto; width: ${HEATFAN_THUMB}px; height: 44px;
          box-sizing: border-box; border-radius: 8px; background: #fff; border: 3px solid var(--c); cursor: grab;
          box-shadow: 0 1px 4px rgba(0,0,0,.3); }
        input[type=range]::-moz-range-thumb { pointer-events: auto; width: ${HEATFAN_THUMB}px; height: 44px; box-sizing: border-box;
          border-radius: 8px; background: #fff; border: 3px solid var(--c); cursor: grab; box-shadow: 0 1px 4px rgba(0,0,0,.3); }
        .section.temp { --c: ${HEATFAN_RANGES.temp.color}; --tint: ${HEATFAN_RANGES.temp.tint}; }
        .section.speed { --c: ${HEATFAN_RANGES.speed.color}; --tint: ${HEATFAN_RANGES.speed.tint}; }
        .actions { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 12px; margin-top: 8px; }
        button.save { border: none; cursor: pointer; background: #cc0000; color: #fff; font: inherit; font-weight: 700; font-size: 17px;
          padding: 12px 44px; border-radius: 999px; }
        button.save:disabled { opacity: .35; cursor: default; }
        button.sec { cursor: pointer; border: 2px solid var(--divider-color, #ccc); background: transparent; color: var(--primary-text-color, #212121);
          font: inherit; font-weight: 600; padding: 9px 16px; border-radius: 999px; }
        button.sec:disabled { opacity: .5; cursor: default; }
        .msg { text-align: center; min-height: 22px; margin-top: 10px; font-size: 14px; }
        .msg.ok { color: #2ea043; } .msg.err { color: #cc0000; } .msg.info { color: var(--secondary-text-color, #727272); }
        .empty { color: var(--secondary-text-color, #727272); padding: 8px 0; }
        .hidden { display: none !important; }
      </style>
      <ha-card>
        <div class="head"><div class="title"></div><select class="ctrl"></select></div>
        <div class="empty hidden"></div>
        <div class="body">
          <div class="tabs"></div>
          ${this._sectionHtml("temp")}
          ${this._sectionHtml("speed")}
          <div class="actions">
            <button class="save"></button>
            <button class="sec undo"></button>
            <button class="sec activate"></button>
          </div>
          <div class="msg"></div>
        </div>
      </ha-card>`;

    for (const kind of Object.keys(HEATFAN_RANGES)) {
      const f = HEATFAN_RANGES[kind];
      const sec = r.querySelector(".section." + kind);
      const loR = sec.querySelector(".r.lo");
      const hiR = sec.querySelector(".r.hi");
      const loN = sec.querySelector(".num.lo");
      const hiN = sec.querySelector(".num.hi");
      loR.addEventListener("input", (e) => this._change(kind, "lo", e.target.value));
      hiR.addEventListener("input", (e) => this._change(kind, "hi", e.target.value));
      loN.addEventListener("change", (e) => this._change(kind, "lo", e.target.value));
      hiN.addEventListener("change", (e) => this._change(kind, "hi", e.target.value));
    }
    r.querySelector(".save").addEventListener("click", () => this._save());
    r.querySelector(".undo").addEventListener("click", () => this._undo());
    r.querySelector(".activate").addEventListener("click", () => this._activate());
    r.querySelector("select.ctrl").addEventListener("change", (e) => {
      this._ctrl = e.target.value;
      this._mode = null;
      this._sync();
    });
    this._built = true;
  }

  _sectionHtml(kind) {
    const f = HEATFAN_RANGES[kind];
    return `
      <div class="section ${kind}">
        <div class="label" data-label="${kind}"></div>
        <div class="row">
          <input class="num lo" type="number" min="${f.min}" max="${f.max}" step="1">
          <div class="dual">
            <div class="track"></div><div class="fill"></div>
            <input class="r lo" type="range" min="${f.min}" max="${f.max}" step="1">
            <input class="r hi" type="range" min="${f.min}" max="${f.max}" step="1">
          </div>
          <input class="num hi" type="number" min="${f.min}" max="${f.max}" step="1">
        </div>
        <div class="limits"><span>${f.min}${f.unit}</span><span></span><span>${f.max}${f.unit}</span></div>
      </div>`;
  }

  // ---------- gegevens bijhouden ----------
  _sync() {
    if (!this._hass) return;
    if (!this._built) this._build();
    const r = this.shadowRoot;
    const found = this._discover();
    const ids = Object.keys(found);
    const t = this._t;

    r.querySelector(".empty").textContent = t.none;
    r.querySelector(".empty").classList.toggle("hidden", ids.length > 0);
    r.querySelector(".body").classList.toggle("hidden", ids.length === 0);
    if (!ids.length) {
      r.querySelector(".title").textContent = this._config.title || t.title;
      r.querySelector("select.ctrl").classList.add("hidden");
      return;
    }

    if (!this._ctrl || !found[this._ctrl]) this._ctrl = ids[0];
    this._found = found;
    const c = found[this._ctrl];
    const active = this._activeMode(c);
    if (this._mode == null) this._mode = active || 1;

    // titel en keuze van controller
    const base = this._config.title || t.title;
    r.querySelector(".title").textContent = c.room ? base + " \u00b7 " + c.room : base;
    const sel = r.querySelector("select.ctrl");
    const showSel = ids.length > 1 && !this._config.controller;
    sel.classList.toggle("hidden", !showSel);
    if (showSel) {
      sel.innerHTML = ids.map((id) => `<option value="${id}">${found[id].room ? found[id].room + " \u00b7 " : ""}${id}</option>`).join("");
      sel.value = this._ctrl;
    }

    // tabs
    const tabs = r.querySelector(".tabs");
    if (tabs.children.length !== 6) {
      tabs.innerHTML = "";
      for (let n = 1; n <= 6; n++) {
        const b = document.createElement("button");
        b.className = "tab";
        b.dataset.mode = String(n);
        b.innerHTML = `<span class="name"></span><span class="dot"></span>`;
        b.addEventListener("click", () => {
          this._mode = n;
          this._sync();
        });
        tabs.appendChild(b);
      }
    }
    for (const b of tabs.children) {
      const n = parseInt(b.dataset.mode, 10);
      b.querySelector(".name").textContent = t.mode + " " + n;
      b.classList.toggle("sel", n === this._mode);
      b.classList.toggle("act", n === active);
    }

    // labels en knoppen
    r.querySelector('[data-label="temp"]').textContent = t.temperature;
    r.querySelector('[data-label="speed"]').textContent = t.speed;
    r.querySelector(".save").textContent = t.save;
    r.querySelector(".undo").textContent = t.undo;
    const act = r.querySelector(".activate");
    act.textContent = this._mode === active ? t.active : t.activate + " " + this._mode;
    act.disabled = this._mode === active || !c.select;

    // waarden uit Home Assistant overnemen zolang er niets is aangepast
    const key = this._key();
    if (!this._dirty[key]) this._draft[key] = this._readFromStates(c, this._mode);
    this._renderValues();
  }

  _renderValues() {
    const r = this.shadowRoot;
    const key = this._key();
    const d = this._draft[key];
    const ok = this._complete(d);
    for (const kind of Object.keys(HEATFAN_RANGES)) {
      const f = HEATFAN_RANGES[kind];
      const sec = r.querySelector(".section." + kind);
      const els = sec.querySelectorAll("input");
      els.forEach((el) => (el.disabled = !ok));
      if (!ok) continue;
      const lo = d[f.lo];
      const hi = d[f.hi];
      sec.querySelector(".r.lo").value = lo;
      sec.querySelector(".r.hi").value = hi;
      sec.querySelector(".num.lo").value = lo;
      sec.querySelector(".num.hi").value = hi;
      const span = f.max - f.min;
      const pl = (lo - f.min) / span;
      const ph = (hi - f.min) / span;
      const fill = sec.querySelector(".fill");
      // vulling loopt van het midden van de ene greep tot het midden van de andere
      fill.style.left = `calc(${pl * 100}% + ${(0.5 - pl) * HEATFAN_THUMB}px)`;
      fill.style.right = `calc(${(1 - ph) * 100}% - ${(0.5 - ph) * HEATFAN_THUMB}px)`;
      // zijn beide grepen bij elkaar aan het einde, dan moet de linker bovenop liggen
      sec.querySelector(".r.lo").style.zIndex = lo > f.min + span / 2 ? 4 : 2;
      sec.querySelector(".r.hi").style.zIndex = 3;
    }
    const dirty = !!this._dirty[key];
    r.querySelector(".save").disabled = !dirty || !ok;
    r.querySelector(".undo").classList.toggle("hidden", !dirty);
    if (dirty) {
      if (this._msgKind !== "err") this._message(this._t.unsaved, "info", true);
    }
    else if (this._msgKind === "info") this._message("", "info", true);
  }

  _change(kind, which, raw) {
    const f = HEATFAN_RANGES[kind];
    const key = this._key();
    const d = this._draft[key];
    if (!this._complete(d)) return;
    let v = Math.round(Number(raw));
    if (!Number.isFinite(v)) {
      this._renderValues();
      return;
    }
    v = Math.min(f.max, Math.max(f.min, v));
    if (which === "lo") d[f.lo] = Math.min(v, d[f.hi]);
    else d[f.hi] = Math.max(v, d[f.lo]);
    this._dirty[key] = true;
    this._renderValues();
  }

  _undo() {
    const key = this._key();
    this._dirty[key] = false;
    this._message("", "info", true);
    this._sync();
  }

  async _save() {
    const key = this._key();
    const d = this._draft[key];
    if (!this._complete(d)) return;
    const data = {
      controller: this._ctrl,
      mode: this._mode,
      start_temp: d["start-temp"],
      max_temp: d["max-temp"],
      start_speed: d["start-speed"],
      max_speed: d["max-speed"],
    };
    try {
      await this._hass.callService("heatfan", "set_curve", data);
      this._dirty[key] = false;
      this._message(this._t.saved + " \u2713", "ok");
      this._sync();
    } catch (err) {
      this._message(this._t.error + ": " + ((err && err.message) || err), "err");
    }
  }

  async _activate() {
    const c = this._found && this._found[this._ctrl];
    if (!c || !c.select) return;
    try {
      await this._hass.callService("select", "select_option", { entity_id: c.select, option: String(this._mode) });
    } catch (err) {
      this._message((err && err.message) || String(err), "err");
    }
  }

  _message(text, kind, keep) {
    const el = this.shadowRoot.querySelector(".msg");
    el.textContent = text;
    el.className = "msg " + kind;
    this._msgKind = kind;
    clearTimeout(this._msgTimer);
    if (!keep && text) {
      this._msgTimer = setTimeout(() => {
        el.textContent = "";
        this._msgKind = null;
      }, 4000);
    }
  }
}

if (!customElements.get("heatfan-card")) {
  customElements.define("heatfan-card", HeatfanCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "heatfan-card")) {
  window.customCards.push({
    type: "heatfan-card",
    name: "Heatfan",
    description: "Temperatuur- en snelheidsbereik per modus met twee schuifregelaars (onofficieel).",
  });
}
