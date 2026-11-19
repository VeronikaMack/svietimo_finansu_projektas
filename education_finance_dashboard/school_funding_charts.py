import pandas as pd
import streamlit as st

CHART_HTML = """
<div id="school-funding-rankings">
  <section class="rank-panel" aria-label="School funding rankings">
    <form class="rank-search" autocomplete="off">
      <label for="rank-school-query">Find a school in both charts</label>
      <div>
        <input id="rank-school-query" type="search" list="rank-school-names" placeholder="Search by school name">
        <datalist id="rank-school-names"></datalist>
        <button type="submit">Find school</button>
      </div>
    </form>
    <p class="rank-status" aria-live="polite"></p>
    <div class="rank-charts">
      <section data-metric="funding" aria-labelledby="rank-funding-title">
        <div class="rank-chart-head">
          <h3 id="rank-funding-title">Total funding</h3>
          <select aria-label="Sort by total funding">
            <option value="desc">Highest first</option>
            <option value="asc">Lowest first</option>
          </select>
        </div>
        <div class="rank-scale" aria-hidden="true"><span data-scale-start></span><span data-scale-end></span></div>
        <div class="rank-scroll" role="region" tabindex="0" aria-label="Scrollable total funding chart">
          <ol aria-label="Schools ranked by total funding"></ol>
        </div>
      </section>
      <section data-metric="perStudent" aria-labelledby="rank-student-title">
        <div class="rank-chart-head">
          <h3 id="rank-student-title">Funding per student</h3>
          <select aria-label="Sort by funding per student">
            <option value="desc">Highest first</option>
            <option value="asc">Lowest first</option>
          </select>
        </div>
        <div class="rank-scale" aria-hidden="true"><span data-scale-start></span><span data-scale-end></span></div>
        <div class="rank-scroll" role="region" tabindex="0" aria-label="Scrollable funding per student chart">
          <ol aria-label="Schools ranked by funding per student"></ol>
        </div>
      </section>
    </div>
  </section>
</div>
"""


CHART_CSS = """
  #school-funding-rankings .rank-panel {
    --ink: var(--st-text-color);
    --muted: color-mix(in srgb, var(--st-text-color) 76%, var(--st-background-color));
    --line: var(--st-dataframe-border-color);
    --input: var(--st-secondary-background-color);
    --selected: var(--st-yellow-background-color);
    --selected-edge: var(--st-orange-color);
    color: var(--ink);
    font: 14px/1.4 var(--st-font, system-ui);
  }
  #school-funding-rankings h3, #school-funding-rankings p { margin: 0; }
  #school-funding-rankings h3 { font-size: 16px; font-weight: 650; }
  #school-funding-rankings .rank-count { color: var(--muted); }
  #school-funding-rankings .rank-search { max-width: 420px; }
  #school-funding-rankings label { display: block; margin-bottom: 4px; font-weight: 600; }
  #school-funding-rankings .rank-search > div { display: flex; gap: 6px; }
  #school-funding-rankings input, #school-funding-rankings select, #school-funding-rankings button {
    box-sizing: border-box;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--input);
    color: var(--ink);
    min-height: 34px;
    padding: 5px 8px;
    font: inherit;
  }
  #school-funding-rankings input { flex: 1; min-width: 0; }
  #school-funding-rankings button { font-weight: 650; white-space: nowrap; }
  #school-funding-rankings .rank-status { margin: 5px 0 10px; color: var(--muted); }
  #school-funding-rankings .rank-status:empty { display: none; }
  #school-funding-rankings .rank-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: clamp(16px, 2.5vw, 32px); margin-top: 14px; }
  #school-funding-rankings .rank-chart-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; min-height: 34px; }
  #school-funding-rankings .rank-scale { display: flex; justify-content: space-between; margin: 0 17px 4px calc(14px + 2.4em); color: var(--muted); font-size: 11px; }
  #school-funding-rankings .rank-scroll { max-height: 360px; overflow-y: scroll; scrollbar-gutter: stable; border-block: 1px solid var(--line); }
  #school-funding-rankings ol { margin: 0; padding: 0; list-style: none; }
  #school-funding-rankings li {
    display: grid;
    grid-template-columns: 2.4em minmax(0, 1fr);
    gap: 6px;
    padding: 7px 8px;
    border-bottom: 1px solid var(--line);
  }
  #school-funding-rankings li:last-child { border-bottom: 0; }
  #school-funding-rankings li[data-highlighted] { background: var(--selected); box-shadow: inset 3px 0 var(--selected-edge); }
  #school-funding-rankings .rank-number { color: var(--muted); font-variant-numeric: tabular-nums; font-weight: 650; }
  #school-funding-rankings .rank-info { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 2px 8px; }
  #school-funding-rankings button.rank-school {
    min-height: 0;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--st-link-color, var(--ink));
    font-weight: 650;
    overflow-wrap: anywhere;
    text-align: left;
    text-decoration: underline;
    text-underline-offset: 2px;
    white-space: normal;
  }
  #school-funding-rankings .rank-count { display: block; font-size: 12px; }
  #school-funding-rankings .rank-amount { white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 600; }
  #school-funding-rankings .rank-track { position: relative; height: 7px; margin-top: 5px; }
  #school-funding-rankings .rank-bar { position: absolute; display: block; height: 100%; border-radius: 2px; background: var(--st-blue-color); }
  #school-funding-rankings [data-metric="perStudent"] .rank-bar { background: var(--st-green-color); }
  @media (max-width: 700px) {
    #school-funding-rankings .rank-charts { grid-template-columns: minmax(0, 1fr); }
    #school-funding-rankings .rank-scroll { max-height: 240px; }
  }
  @media (pointer: coarse) {
    #school-funding-rankings input, #school-funding-rankings select, #school-funding-rankings button { min-height: 44px; font-size: 16px; }
  }
"""


CHART_JS = r"""
export default function renderSchoolFunding({parentElement, data, setTriggerValue}) {
  const root = parentElement.querySelector("#school-funding-rankings");
  const form = root.querySelector("form");
  const input = form.querySelector("input");
  const options = form.querySelector("datalist");
  const status = root.querySelector(".rank-status");
  const schools = data.schools;
  const byName = (left, right) => left.name.localeCompare(right.name, "lt") ||
    left.id.localeCompare(right.id, undefined, {numeric: true});
  const fold = text => text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();
  const amountFormat = new Intl.NumberFormat("en-IE", {
    style: "currency", currency: "EUR", maximumFractionDigits: 0,
  });
  const rateFormat = new Intl.NumberFormat("en-IE", {style: "currency", currency: "EUR"});
  const countFormat = new Intl.NumberFormat("en-IE");
  const nameCounts = new Map();
  for (const school of schools) {
    const name = fold(school.name);
    nameCounts.set(name, (nameCounts.get(name) ?? 0) + 1);
  }
  const searchLabel = school => nameCounts.get(fold(school.name)) > 1
    ? school.name + " (" + school.id + ")"
    : school.name;

  let selected = null;
  input.value = "";
  status.textContent = "";

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  options.replaceChildren(...[...schools].sort(byName).map(school => {
    const option = document.createElement("option");
    option.value = searchLabel(school);
    return option;
  }));

  const charts = [...root.querySelectorAll("[data-metric]")].map(section => {
    const metric = section.dataset.metric;
    const format = metric === "funding" ? amountFormat : rateFormat;
    const ranked = schools.filter(school => school[metric] !== null).sort(
      (left, right) => right[metric] - left[metric] || byName(left, right),
    );
    const unranked = schools.filter(school => school[metric] === null).sort(byName);
    const ranks = new Map();
    let rank = 0;
    ranked.forEach((school, index) => {
      if (!index || school[metric] !== ranked[index - 1][metric]) rank = index + 1;
      ranks.set(school.id, rank);
    });

    const minimum = Math.min(0, ranked.at(-1)?.[metric] ?? 0);
    const maximum = Math.max(0, ranked[0]?.[metric] ?? 0);
    const range = maximum - minimum || 1;
    const percent = value => 100 * (value - minimum) / range;
    section.querySelector("[data-scale-start]").textContent = ranked.length ? format.format(minimum) : "";
    section.querySelector("[data-scale-end]").textContent = maximum !== minimum ? format.format(maximum) : "";

    const sort = section.querySelector("select");
    const scroll = section.querySelector(".rank-scroll");
    const list = scroll.querySelector("ol");

    function render() {
      const ordered = sort.value === "asc"
        ? [...ranked].sort((left, right) => left[metric] - right[metric] || byName(left, right))
        : ranked;
      let highlighted = null;
      const rows = [...ordered, ...unranked].map(school => {
        const row = document.createElement("li");
        if (school.id === selected) {
          row.dataset.highlighted = "";
          highlighted = row;
        }
        const schoolRank = ranks.get(school.id);
        const rankLabel = element("span", "rank-number", schoolRank ? "#" + schoolRank : "—");
        if (!schoolRank) rankLabel.setAttribute("aria-label", "Unranked");

        const info = element("div", "rank-info");
        const description = document.createElement("div");
        const count = school.students === null
          ? "Student count missing"
          : countFormat.format(school.students) + " students";
        const schoolButton = element("button", "rank-school", searchLabel(school));
        schoolButton.type = "button";
        schoolButton.setAttribute("aria-label", "Open School Explorer for " + searchLabel(school));
        schoolButton.onclick = () => setTriggerValue("open_school", Number(school.id));
        description.append(schoolButton, element("span", "rank-count", count));

        const content = document.createElement("div");
        const value = school[metric];
        info.append(description, element("span", "rank-amount", value === null ? "Unavailable" : format.format(value)));
        content.append(info);
        if (value !== null) {
          const track = element("div", "rank-track");
          track.setAttribute("aria-hidden", "true");
          const bar = element("span", "rank-bar");
          bar.style.left = percent(Math.min(0, value)) + "%";
          bar.style.width = (100 * Math.abs(value) / range) + "%";
          track.append(bar);
          content.append(track);
        }
        row.append(rankLabel, content);
        return row;
      });
      list.replaceChildren(...rows);
      if (highlighted) {
        const relativeTop = highlighted.getBoundingClientRect().top - scroll.getBoundingClientRect().top;
        scroll.scrollTop += relativeTop - (scroll.clientHeight - highlighted.offsetHeight) / 2;
      } else {
        scroll.scrollTop = 0;
      }
    }

    sort.onchange = render;
    render();
    return {ranks, render};
  });

  function clearSearch() {
    status.textContent = "";
    if (selected !== null) {
      selected = null;
      charts.forEach(chart => chart.render());
    }
  }

  input.oninput = () => {
    if (!input.value.trim()) clearSearch();
  };
  form.onsubmit = event => {
    event.preventDefault();
    const query = fold(input.value);
    if (!query) {
      clearSearch();
      return;
    }
    const exact = schools.filter(school => fold(searchLabel(school)) === query);
    const matches = schools.filter(school => fold(searchLabel(school)).includes(query));
    const school = exact[0] ?? (matches.length === 1 ? matches[0] : null);
    if (!school) {
      clearSearch();
      status.textContent = matches.length
        ? "Several schools match. Choose a suggestion or enter the full name."
        : "No school matches that name in the current filters.";
      return;
    }
    selected = school.id;
    input.value = searchLabel(school);
    charts.forEach(chart => chart.render());

    const totalRank = charts[0].ranks.get(selected);
    const perStudentRank = charts[1].ranks.get(selected);
    const perStudentStatus = perStudentRank ? "#" + perStudentRank + " in funding per student" : "unranked for funding per student";
    status.textContent = searchLabel(school) + " · #" + totalRank + " in total funding · " + perStudentStatus;
  };
}
"""


school_funding_charts = st.components.v2.component(
    "school_funding_charts",
    html=CHART_HTML,
    css=CHART_CSS,
    js=CHART_JS,
)


def show_school_funding_charts(schools):
    data = []
    for school in schools.itertuples(index=False):
        code = str(int(school.mokyklos_kodas))
        students = int(school.students) if pd.notna(school.students) else None
        funding = float(school.funding)
        name = school.mokykla.strip() if isinstance(school.mokykla, str) else ""
        data.append(
            {
                "id": code,
                "name": name or f"School {code}",
                "students": students,
                "funding": funding,
                "perStudent": (
                    funding / students
                    if students is not None and students > 0
                    else None
                ),
            }
        )

    result = school_funding_charts(
        data={"schools": data},
        key="explorer_school_funding",
        on_open_school_change=lambda: None,
    )
    return result.open_school
