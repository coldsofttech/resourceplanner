"""
apps/projects/ai.py
--------------------
Project-domain AI logic.  This module owns everything that is specific to
generating project labels with AI:

  - Building the prompt (with DB context: existing labels, sibling labels)
  - Parsing and sanitising the model's response
  - Orchestrating the AI call and delegating fallback to ProjectLabelService

It imports the generic AI client from apps.ai.client and the deterministic
engine from apps.projects.engines.  It has no knowledge of views, serializers,
or HTTP — those concerns stay in api_views.py.

Public interface (called by ProjectLabelService in services.py):

    ProjectLabelAI.suggest(project: Project) -> str

Always returns a valid, collision-resolved label string.  Never raises.
"""

import logging
import re

logger = logging.getLogger(__name__)


class ProjectLabelAI:

    @staticmethod
    def suggest(project) -> str:
        """
        Called by ProjectLabelService.suggest_label() only when AI_ENABLED=true.

        Attempts the AI path.  On any failure, logs a warning and delegates to
        ProjectLabelService._suggest_deterministic() — keeping the fallback
        logic in one canonical place in services.py.

        Always returns a valid collision-resolved label string.
        """
        try:
            return ProjectLabelAI._ai(project)
        except Exception as exc:
            logger.warning(
                "ProjectLabelAI: AI call failed for project pk=%s — "
                "falling back to deterministic engine. Error: %s",
                project.pk,
                exc,
                exc_info=True,
            )
            from apps.projects.services import ProjectLabelService

            return ProjectLabelService._suggest_deterministic(project)

    # ── AI path ───────────────────────────────────────────────────────────────

    @staticmethod
    def _ai(project) -> str:
        """Build prompt → call AI → parse → resolve collision → return label."""
        from apps.ai.client import AIClientFactory
        from apps.projects.engines import ProjectLabelEngineService

        prompt = ProjectLabelAI._build_prompt(project)

        client = AIClientFactory.get_client()
        raw = client.complete(prompt, max_tokens=60)

        label = ProjectLabelAI._parse_response(raw)
        return ProjectLabelEngineService.resolve_collision(label)

    # ── Prompt builder ────────────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(project) -> str:
        """
        Build a detailed prompt that gives the model full context:
          - What a label is and how it is used in this system
          - All formatting rules (uppercase, max 20 chars, allowed chars)
          - Programme prefix convention with all four cases
          - Up to 30 existing sibling labels (collision avoidance)
          - Up to 50 cross-programme labels (naming style reference)
          - Deterministic candidates as a hint the model may use or improve on
          - Strict single-line output instruction
        """
        from apps.projects.engines import ProjectLabelEngineService
        from apps.projects.models import ProjectLabel

        programme_name = (
            project.programme.name
            if hasattr(project, "programme") and project.programme
            else None
        )

        # Deterministic candidates — surfaced as a hint, not a constraint
        det_candidates = ProjectLabelEngineService.build_candidates(
            programme_name, project.name
        )
        det_hint = ", ".join(det_candidates[:3]) if det_candidates else "none"

        # Labels in the same programme — primary collision avoidance context
        sibling_qs = ProjectLabel.objects.select_related("project__programme")
        if programme_name:
            sibling_qs = sibling_qs.filter(project__programme__name=programme_name)
        sibling_labels = list(
            sibling_qs.values_list("label", flat=True).order_by("label")[:30]
        )

        # Broader cross-programme sample — naming convention reference
        all_labels = list(
            ProjectLabel.objects.values_list("label", flat=True).order_by("label")[:50]
        )

        programme_line = (
            f"Programme      : {programme_name}"
            if programme_name and programme_name.strip().upper() != "OTHERS"
            else "Programme      : None (no programme — omit prefix entirely)"
        )

        sibling_block = (
            "\n".join(f"  - {lbl}" for lbl in sibling_labels)
            if sibling_labels
            else "  (none yet)"
        )
        all_labels_block = (
            "\n".join(f"  - {lbl}" for lbl in all_labels)
            if all_labels
            else "  (none yet)"
        )

        return f"""
You are a project label generator for an internal project tracking system used
by a software delivery organisation.  Your task is to generate a single short
label that uniquely identifies a project in this system.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT A LABEL IS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A label is a short human-readable code used in dashboards, exports, and
resource planning grids.  It must be instantly recognisable to someone who
knows the project name.  Examples: CCD_PORTAL, XTY2_MIGR, PLAT_API_GW.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT FORMATTING RULES  (all must be satisfied)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.  UPPERCASE only — A–Z, 0–9, and underscores (_) are the only permitted
    characters.  No spaces, hyphens, dots, or lowercase letters.
2.  Maximum 20 characters (including underscores).
3.  Minimum 2 characters.
4.  Must NOT match any label in the EXISTING LABELS lists below.
5.  Do not add a numeric suffix (e.g. _2) unless no other meaningful variation
    is available — prefer a different word abbreviation first.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROGRAMME PREFIX CONVENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Known acronym (all-uppercase, e.g. CCD, XTY) → use verbatim: CCD_<slug>
- Acronym with version (e.g. XTY 2.0 or XTY2.0) → merge: XTY2_<slug>
- Mixed-case words (e.g. "Customer Platform") → initials: CP_<slug>
- No programme or programme is "Others" → no prefix, slug only
- Prefix and slug are separated by exactly one underscore.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT SLUG GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Use 1–4 meaningful abbreviations from the project name joined by underscores.
- Skip stop words: a, an, the, of, from, to, in, on, at, by, for, and, or,
  but, with, into, onto, upon, as, is, are, was, were, be, been, being, that,
  this, these, those, it, its, via, per.
- Prefer domain / noun words that make the label instantly recognisable.
- If the project name is already an acronym, use it directly.
- Keep total label length within 20 characters — shorten slugs if needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{programme_line}
Project name   : {project.name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXISTING LABELS IN THIS PROGRAMME  (must not clash)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{sibling_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALL LABELS IN THE SYSTEM  (naming style reference — also must not clash)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{all_labels_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DETERMINISTIC ENGINE SUGGESTIONS  (reference only — improve on these if you can)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{det_hint}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT  (critical)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Respond with EXACTLY ONE LINE containing only the label.
No explanation, no punctuation, no markdown, no quotes.
Valid example response:
XTY2_CUST_PORT
""".strip()

    # ── Response parser ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> str:
        """
        Sanitise the model's raw text into a valid label string.

        Steps:
          1. Take only the first non-empty line (model may add explanation
             on subsequent lines despite the prompt instruction).
          2. Strip surrounding whitespace and quotes.
          3. Uppercase everything.
          4. Replace any run of non-alphanumeric characters with underscore.
          5. Strip leading/trailing underscores.
          6. Truncate to 20 characters without cutting mid-segment.
          7. Raise ValueError if result is too short — caller falls back
             to the deterministic engine.
        """
        first_line = next(
            (line.strip() for line in raw.splitlines() if line.strip()), ""
        )
        first_line = first_line.strip("\"'`")
        label = first_line.upper()
        label = re.sub(r"[^A-Z0-9]+", "_", label)
        label = label.strip("_")

        if len(label) > 20:
            label = label[:20].rstrip("_")

        if len(label) < 2:
            raise ValueError(
                f"AI returned an unusable label after sanitisation: {repr(raw)}"
            )

        return label
