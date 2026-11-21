"""One hoverable, keyboard-accessible help bubble beside each school filter."""
import streamlit as st
from special_school_comparison import show_special_school_explanation

SPECIAL_SCHOOL_HELP = (
    "Special schools include special schools, children's socialisation centres, "
    "and sanatorium or hospital schools in the dataset. Regular schools may also "
    "teach pupils with special educational needs."
)

HELP_HTML = """
<div class="special-help">
  <button class="special-help-icon" type="button" aria-label="About special schools" aria-expanded="false">?</button>
  <div class="special-help-bubble" role="dialog" aria-label="Special-school explanation" hidden>
    <p class="special-help-definition"></p>
    <details>
      <summary>Why offer exclusion?</summary>
      <p>These institutions serve different educational and support needs. Their funding per student can differ from other schools. Excluding them provides a comparison of the remaining schools; it does not imply that their funding is excessive.</p>
      <button type="button" class="special-help-comparison">View the national comparison</button>
    </details>
  </div>
</div>
"""
HELP_CSS = """
.special-help { display: inline-block; width: 28px; height: 28px; font: 14px/1.5 var(--st-font, system-ui); color: var(--st-text-color, #334155); }
.special-help-icon { display: block; width: 22px; height: 22px; padding: 0; border: 1.7px solid currentColor; border-radius: 50%; background: transparent; color: inherit; font: bold 14px/1 system-ui; cursor: help; opacity: .75; }
.special-help-icon:focus-visible { outline: 2px solid var(--st-primary-color, #2563eb); outline-offset: 3px; }
.special-help-bubble { position: fixed; z-index: 100000; box-sizing: border-box; width: 360px; max-width: calc(100vw - 24px); max-height: 65vh; overflow-y: auto; padding: 16px; background: var(--st-secondary-background-color, #f1f5f9); color: inherit; border: 1px solid var(--st-border-color, #94a3b8); border-radius: 10px; box-shadow: 0 5px 22px #0003; }
.special-help-bubble[hidden] { display: none; }
.special-help-bubble p { margin: 0 0 12px; }
.special-help-bubble summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
.special-help-bubble details[open] summary { margin-bottom: 8px; }
.special-help-comparison { padding: 7px 10px; border: 1px solid currentColor; border-radius: 6px; color: inherit; background: transparent; cursor: pointer; font: inherit; }
"""
HELP_JS = r"""
export default function({parentElement, data, setTriggerValue}) {
  const root = parentElement.querySelector('.special-help');
  const icon = root.querySelector('.special-help-icon');
  const bubble = root.querySelector('.special-help-bubble');
  const comparison = root.querySelector('.special-help-comparison');
  root.querySelector('.special-help-definition').textContent = data.definition;
  let closeTimer;
  function position() {
    const rect = icon.getBoundingClientRect();
    const width = Math.min(360, window.innerWidth - 24);
    bubble.style.width = width + 'px';
    bubble.style.left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)) + 'px';
    const height = bubble.getBoundingClientRect().height;
    const below = rect.bottom + 8;
    bubble.style.top = (below + height <= window.innerHeight - 12 ? below : Math.max(12, rect.top - height - 8)) + 'px';
  }
  function open() { clearTimeout(closeTimer); bubble.hidden = false; icon.setAttribute('aria-expanded', 'true'); position(); }
  function close() { bubble.hidden = true; icon.setAttribute('aria-expanded', 'false'); }
  function later() { clearTimeout(closeTimer); closeTimer = setTimeout(() => { if (!root.contains(document.activeElement)) close(); }, 250); }
  function outside(event) { if (!root.contains(event.target)) close(); }
  function escape(event) { if (event.key === 'Escape') { icon.focus(); close(); event.preventDefault(); } }
  const scroll = () => { if (!bubble.hidden) position(); };
  root.addEventListener('mouseenter', open);
  root.addEventListener('mouseleave', later);
  root.addEventListener('focusin', open);
  root.addEventListener('focusout', later);
  root.addEventListener('keydown', escape);
  icon.onclick = open;
  bubble.querySelector('details').addEventListener('toggle', position);
  comparison.onclick = () => { close(); setTriggerValue('show_comparison', true); };
  document.addEventListener('pointerdown', outside);
  window.addEventListener('resize', scroll);
  window.addEventListener('scroll', scroll, true);
  return () => {
    clearTimeout(closeTimer);
    document.removeEventListener('pointerdown', outside);
    window.removeEventListener('resize', scroll);
    window.removeEventListener('scroll', scroll, true);
  };
}
"""
special_school_help = st.components.v2.component(
    "special_school_hover_help", html=HELP_HTML, css=HELP_CSS, js=HELP_JS,
    isolate_styles=False,
)

@st.dialog("Why offer the option to exclude special schools?", width="large")
def special_school_dialog(funding, year):
    show_special_school_explanation(funding, year)


def special_school_filter(funding, year, key, value=True, on_change=None):
    if key not in st.session_state:
        st.session_state[key] = value
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        selected = st.toggle(
            "Include special schools", key=key,
            on_change=on_change, persist_state="session", width="content",
        )
        result = special_school_help(
            data={"definition": SPECIAL_SCHOOL_HELP}, key=f"{key}_help",
            width=28, height=28, on_show_comparison_change=lambda: None,
        )
        if result.show_comparison:
            special_school_dialog(funding, year)
    return selected
