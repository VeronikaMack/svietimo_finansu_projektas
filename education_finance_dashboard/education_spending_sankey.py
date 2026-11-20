import json

import streamlit as st
from plotly.offline import get_plotlyjs


SANKEY_HTML = """
<div class="education-spending-explorer">
  <nav class="spending-navigation" aria-label="Diagram navigation">
    <button type="button" data-back>← Back</button>
    <button type="button" data-home>⌂ Overall view</button>
  </nav>
  <nav class="spending-trail" aria-label="Selected expenditure category"></nav>
  <p class="spending-total" aria-live="polite"></p>
  <div class="spending-chart" role="group" aria-label="Education expenditure flows"></div>
  <p class="spending-status" role="status"></p>
</div>
"""

SANKEY_CSS = """
.education-spending-explorer {
  color: var(--st-text-color, #334155);
  font: 14px/1.5 var(--st-font, system-ui);
  width: 100%;
}
.education-spending-explorer .spending-navigation {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.education-spending-explorer button {
  font: inherit;
  color: inherit;
  background: var(--st-secondary-background-color, #f1f5f9);
  border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
}
.education-spending-explorer button:disabled { opacity: 0.45; cursor: default; }
.education-spending-explorer button:focus-visible,
.education-spending-explorer .sankey-node:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 3px;
}
.education-spending-explorer .spending-trail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
}
.education-spending-explorer .spending-trail button {
  background: transparent;
  border: 0;
  padding: 0;
  text-decoration: underline;
}
.education-spending-explorer .spending-total { margin: 10px 0 0; font-weight: 600; }
.education-spending-explorer .spending-chart { width: 100%; min-width: 0; }
.education-spending-explorer .spending-status { margin: 4px 0; }
"""

SANKEY_JS = r"""
export default function renderSpendingSankey({parentElement, data}) {
  const root = parentElement.querySelector('.education-spending-explorer');
  const graph = root.querySelector('.spending-chart');
  const back = root.querySelector('[data-back]');
  const home = root.querySelector('[data-home]');
  const trail = root.querySelector('.spending-trail');
  const total = root.querySelector('.spending-total');
  const status = root.querySelector('.spending-status');
  const nodes = data.nodes;
  const currency = new Intl.NumberFormat('en-IE', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
  });
  let currentId = '0';
  let disposed = false;
  let renderQueue = Promise.resolve();

  function escapeLabel(text) {
    return text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  }

  function nodeLabel(node) {
    const lines = [];
    let line = '';
    for (const word of node.label.split(/\s+/)) {
      if (line && line.length + word.length > 35) {
        lines.push(escapeLabel(line));
        line = '';
      }
      line = line ? line + ' ' + word : word;
    }
    lines.push(escapeLabel(line));
    lines.push(currency.format(node.amount));
    return lines.join('<br>');
  }

  function updateNavigation() {
    const selected = nodes[currentId];
    back.disabled = selected.parent === null;
    home.disabled = currentId === '0';
    total.textContent = selected.label + ' · ' + currency.format(selected.amount);
    const ancestors = [];
    let ancestor = selected;
    while (ancestor) {
      ancestors.unshift(ancestor);
      ancestor = ancestor.parent === null ? null : nodes[ancestor.parent];
    }
    trail.replaceChildren();
    ancestors.forEach((node, index) => {
      if (index) {
        const separator = document.createElement('span');
        separator.textContent = '›';
        separator.setAttribute('aria-hidden', 'true');
        trail.append(separator);
      }
      const element = document.createElement(node.id === currentId ? 'span' : 'button');
      element.textContent = node.label;
      if (node.id !== currentId) {
        element.type = 'button';
        element.onclick = () => showView(node.id);
      } else {
        element.setAttribute('aria-current', 'page');
      }
      trail.append(element);
    });
  }

  function detailFigure(selected) {
    const children = selected.children.map(id => nodes[id]);
    const shown = [selected, ...children];
    return {
      data: [{
        type: 'sankey',
        arrangement: 'fixed',
        node: {
          label: shown.map(nodeLabel),
          customdata: shown.map(node => node.id),
          color: ['#334155', ...children.map(() => '#2563eb')],
          pad: 24,
          thickness: 18,
          hovertemplate: '%{label}<extra></extra>',
        },
        link: {
          source: children.map(() => 0),
          target: children.map((node, index) => index + 1),
          value: children.map(node => node.amount),
          customdata: children.map(node => node.id),
          color: children.map(() => 'rgba(37, 99, 235, 0.35)'),
          hovertemplate: '%{target.label}<extra></extra>',
        },
      }],
      layout: {margin: {l: 12, r: 12, t: 12, b: 12}, font: {size: 12}},
    };
  }

  function activateNodes() {
    const ids = graph.data[0].node.customdata;
    graph.querySelectorAll('.sankey-node').forEach((element, index) => {
      const node = nodes[ids[index]];
      const expandable = node && node.children.length && node.id !== currentId;
      element.style.cursor = expandable ? 'pointer' : 'default';
      if (expandable) {
        element.setAttribute('tabindex', '0');
        element.setAttribute('role', 'button');
        element.setAttribute('aria-label', node.label + ', ' + currency.format(node.amount));
        element.onkeydown = event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            showView(node.id);
          }
        };
      } else {
        element.removeAttribute('tabindex');
        element.removeAttribute('role');
        element.removeAttribute('aria-label');
        element.onkeydown = null;
      }
    });
  }

  function showView(id) {
    const selected = nodes[id];
    if (!selected || !selected.children.length) return;
    currentId = id;
    updateNavigation();
    renderQueue = renderQueue.then(async () => {
      if (disposed || currentId !== id) return;
      const figure = id === '0' ? structuredClone(data.overview) : detailFigure(selected);
      const height = Math.max(440, selected.children.length * 60);
      graph.style.height = height + 'px';
      figure.data[0].arrangement = 'fixed';
      figure.layout = {
        ...figure.layout,
        autosize: true,
        height,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {...figure.layout.font, color: getComputedStyle(root).color},
        separators: '.,',
      };
      await Plotly.react(graph, figure.data, figure.layout, {displayModeBar: false, responsive: true});
      if (!disposed && currentId === id) {
        activateNodes();
        status.textContent = selected.children.some(child => nodes[child].children.length)
          ? 'Categories and flows with further detail can be expanded.'
          : 'The most detailed expenditure level is shown for this category.';
      }
    }).catch(error => {
      if (!disposed) status.textContent = 'Unable to display the diagram - ' + error.message;
    });
  }

  showView('0');
  renderQueue = renderQueue.then(() => {
    if (disposed) return;
    graph.on('plotly_click', event => {
      const id = event.points?.[0]?.customdata;
      if (typeof id === 'string' && id !== currentId) showView(id);
    });
  });
  back.onclick = () => showView(nodes[currentId].parent);
  home.onclick = () => showView('0');
  const resize = new ResizeObserver(() => {
    if (graph.data && !disposed) Plotly.Plots.resize(graph);
  });
  resize.observe(root);
  return () => {
    disposed = true;
    resize.disconnect();
    renderQueue.finally(() => Plotly.purge(graph));
  };
}
"""

# Keep the Plotly bundle local and scoped to this component's module.
PLOTLY_JS = (
    'const plotlyModule = {exports: {}};\n'
    '(function(module) {\n' + get_plotlyjs() + '\n})(plotlyModule);\n'
    'const Plotly = plotlyModule.exports;\n'
)

spending_sankey = st.components.v2.component(
    'education_spending_sankey',
    html=SANKEY_HTML,
    css=SANKEY_CSS,
    js=PLOTLY_JS + SANKEY_JS,
    isolate_styles=False,
)


def show_spending_sankey(overview, nodes):
    spending_sankey(
        data={'overview': json.loads(overview.to_json()), 'nodes': nodes},
        key='education_spending_sankey',
    )
