from __future__ import annotations

from html import escape
import math
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from src.api.schemas import (
    EntityRelationshipsResponse,
    EntitySearchResult,
    HealthResponse,
    RelationshipViewResponse,
    RootResponse,
    StatsResponse,
    relationship_view_response,
    search_result_from_match,
)
from src.api.services import DatasetService
from src.models import Entity, Relationship


TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
DATABASE_TEMPLATE_PATH = Path(__file__).parent / "templates" / "database.html"
ENTITY_DETAIL_TEMPLATE_PATH = Path(__file__).parent / "templates" / "entity_detail.html"
RELATIONSHIPS_TEMPLATE_PATH = Path(__file__).parent / "templates" / "relationships.html"
GRAPH_TEMPLATE_PATH = Path(__file__).parent / "templates" / "graph.html"
GITHUB_URL = "https://github.com/anandvignesh23-rgb/ai-orbit-ingestion"


def create_app(data_dir: str | Path = "data") -> FastAPI:
    dataset_service = DatasetService(data_dir=data_dir)
    app = FastAPI(
        title="AI Orbit Data API",
        description="Public demonstration API for the AI Orbit ingestion pipeline.",
        version="1.0.0",
    )
    app.state.dataset_service = dataset_service

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> HTMLResponse:
        base_url = str(request.base_url).rstrip("/")
        html = _render_landing_page(
            dataset_service.landing_page_context(),
            base_url=base_url,
        )
        return HTMLResponse(content=html)

    @app.get("/info", response_model=RootResponse)
    def info(request: Request) -> RootResponse:
        base_url = str(request.base_url).rstrip("/")
        return RootResponse(
            name="AI Orbit Data Ingestion Pipeline",
            status="online",
            description="API serving normalized AI ecosystem entities and relationships.",
            url=base_url,
            docs=f"{base_url}/docs",
            health=f"{base_url}/health",
            stats=f"{base_url}/stats",
            search=f"{base_url}/search?q=agent",
        )

    @app.get("/database", response_class=HTMLResponse)
    def database(
        q: str | None = Query(default=None),
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=24, ge=1, le=100),
    ) -> HTMLResponse:
        html = _render_database_page(
            dataset_service.database_page_context(
                query=q,
                entity_type=type,
                category=category,
                page=page,
                limit=limit,
            )
        )
        return HTMLResponse(content=html)

    @app.get("/database/relationships", response_class=HTMLResponse)
    def database_relationships(
        relationship_type: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=24, ge=1, le=100),
    ) -> HTMLResponse:
        html = _render_relationships_page(
            dataset_service.relationship_explorer_context(
                relationship_type=relationship_type,
                page=page,
                limit=limit,
            )
        )
        return HTMLResponse(content=html)

    @app.get("/graph", response_class=HTMLResponse)
    def graph(
        q: str | None = Query(default=None),
        entity: str | None = Query(default=None),
        depth: int = Query(default=1, ge=1, le=2),
        type: str | None = Query(default=None),
        relationship_type: str | None = Query(default=None),
        edge: str | None = Query(default=None),
    ) -> HTMLResponse:
        html = _render_graph_page(
            dataset_service.graph_page_context(
                query=q,
                entity_id=entity,
                depth=depth,
                entity_type=type,
                relationship_type=relationship_type,
                edge_id=edge,
            )
        )
        return HTMLResponse(content=html)

    @app.get("/database/{entity_id}", response_class=HTMLResponse)
    def database_entity(entity_id: str) -> HTMLResponse:
        context = dataset_service.entity_detail_context(entity_id)
        if context is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return HTMLResponse(content=_render_entity_detail_page(context))

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            entities_loaded=dataset_service.entities_loaded,
            relationships_loaded=dataset_service.relationships_loaded,
        )

    @app.get("/stats", response_model=StatsResponse)
    def stats() -> StatsResponse:
        return StatsResponse.model_validate(dataset_service.stats())

    @app.get("/entities", response_model=list[Entity])
    def entities(
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> list[Entity]:
        return dataset_service.list_entities(
            entity_type=type,
            category=category,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}", response_model=Entity)
    def entity(entity_id: str) -> Entity:
        found = dataset_service.get_entity(entity_id)
        if found is None:
            raise HTTPException(status_code=404, detail="entity not found")
        return found

    @app.get("/relationships", response_model=list[Relationship])
    def relationships(
        relationship_type: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        target_id: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=100),
    ) -> list[Relationship]:
        return dataset_service.list_relationships(
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            offset=offset,
            limit=limit,
        )

    @app.get("/entities/{entity_id}/relationships", response_model=EntityRelationshipsResponse)
    def entity_relationships(
        entity_id: str,
        relationship_type: str | None = Query(default=None),
    ) -> EntityRelationshipsResponse:
        views = dataset_service.relationship_views_for_entity(
            entity_id,
            relationship_type=relationship_type,
        )
        if views is None:
            raise HTTPException(status_code=404, detail="entity not found")
        responses = [relationship_view_response(view) for view in views]
        return EntityRelationshipsResponse(
            entity_id=entity_id,
            outgoing=[view for view in responses if view.direction == "outgoing"],
            incoming=[view for view in responses if view.direction == "incoming"],
        )

    @app.get("/search", response_model=list[EntitySearchResult])
    def search(
        q: str = Query(min_length=1),
        type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        limit: int = Query(default=10, ge=1, le=100),
    ) -> list[EntitySearchResult]:
        matches = dataset_service.index.search_entities(
            q,
            entity_type=type,
            category=category,
            limit=limit,
        )
        return [search_result_from_match(match) for match in matches]

    return app


def _render_landing_page(context: dict, *, base_url: str) -> str:
    metrics = context["metrics"]
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "BASE_URL": base_url,
        "GITHUB_URL": GITHUB_URL,
        "TOTAL_ENTITIES": str(metrics.get("entities", "N/A")),
        "TOTAL_RELATIONSHIPS": str(metrics.get("relationships", "N/A")),
        "DUPLICATES_MERGED": str(metrics.get("duplicates_merged", "N/A")),
        "VALIDATION_ERRORS": str(metrics.get("validation_errors", "N/A")),
        "ENTITY_TYPE_ROWS": _count_rows(context.get("entity_types", {})),
        "RELATIONSHIP_TYPE_ROWS": _count_rows(context.get("relationship_types", {})),
        "SOURCE_BADGES": _source_badges(context.get("sources", [])),
        "CATEGORY_BADGES": _category_badges(context.get("top_categories", {})),
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _render_database_page(context: dict) -> str:
    template = DATABASE_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "TOTAL_ENTITIES": str(context["total_entities"]),
        "TOTAL_RELATIONSHIPS": str(context["total_relationships"]),
        "RESULT_COUNT": str(context["result_count"]),
        "RESULT_LABEL": escape(context["result_label"]),
        "QUERY": escape(context["query"], quote=True),
        "PAGE": str(context["page"]),
        "TYPE_OPTIONS": _select_options(
            context["entity_types"],
            selected=context["selected_type"],
            empty_label="All types",
        ),
        "CATEGORY_OPTIONS": _select_options(
            context["categories"],
            selected=context["selected_category"],
            empty_label="All categories",
        ),
        "LIMIT_OPTIONS": _limit_options(int(context["limit"])),
        "TYPE_FILTERS": _type_filter_links(context),
        "DATABASE_CARDS": _database_cards(context["rows"]),
        "ACTIVE_FILTERS": _active_filters(context),
        "SHOWING_RANGE": _showing_range(context, noun="entities"),
        "PAGINATION": _pagination(
            path="/database",
            page=context["page"],
            total_pages=context["total_pages"],
            params={
                "q": context["query"],
                "type": context["selected_type"],
                "category": context["selected_category"],
                "limit": context["limit"],
            },
        ),
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _render_entity_detail_page(context: dict) -> str:
    entity = context["entity"]
    template = ENTITY_DETAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "ENTITY_NAME": escape(entity.name),
        "ENTITY_TYPE": escape(_humanize(str(entity.entity_type))),
        "DESCRIPTION": escape(entity.description or "No description available."),
        "OFFICIAL_URL": _official_url(entity),
        "CATEGORIES": _entity_category_pills(entity.categories),
        "PROVIDER": escape(_provider_name(entity) or "N/A"),
        "RELATIONSHIP_COUNT": str(context["relationship_count"]),
        "SOURCE_ROWS": _source_rows(context["sources"]),
        "METADATA_ROWS": _metadata_rows(context["metadata"]),
        "OUTGOING_RELATIONSHIPS": _relationship_view_cards(context["outgoing"]),
        "INCOMING_RELATIONSHIPS": _relationship_view_cards(context["incoming"]),
        "RAW_JSON_URL": f"/entities/{escape(entity.id, quote=True)}",
        "GRAPH_URL": f"/graph?entity={escape(entity.id, quote=True)}",
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _render_relationships_page(context: dict) -> str:
    template = RELATIONSHIPS_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "TOTAL_RELATIONSHIPS": str(context["total_relationships"]),
        "RESULT_COUNT": str(context["result_count"]),
        "RELATIONSHIP_FILTERS": _relationship_filter_links(context),
        "RELATIONSHIP_ROWS": _relationship_explorer_rows(context["rows"]),
        "SHOWING_RANGE": _showing_range(context, noun="relationships"),
        "PAGINATION": _pagination(
            path="/database/relationships",
            page=context["page"],
            total_pages=context["total_pages"],
            params={
                "relationship_type": context["selected_type"],
                "limit": context["limit"],
            },
        ),
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _render_graph_page(context: dict) -> str:
    template = GRAPH_TEMPLATE_PATH.read_text(encoding="utf-8")
    selected = context["selected_entity"]
    replacements = {
        "TOTAL_ENTITIES": str(context["total_entities"]),
        "TOTAL_RELATIONSHIPS": str(context["total_relationships"]),
        "VISIBLE_NODES": str(len(context["nodes"])),
        "VISIBLE_EDGES": str(len(context["edges"])),
        "QUERY": escape(context["query"], quote=True),
        "DEPTH_OPTIONS": _depth_options(context["depth"]),
        "ENTITY_TYPE_OPTIONS": _select_options(
            context["entity_types"],
            selected=context["selected_type"],
            empty_label="All node types",
        ),
        "RELATIONSHIP_TYPE_OPTIONS": _select_options(
            context["relationship_types"],
            selected=context["selected_relationship_type"],
            empty_label="All relationship types",
        ),
        "GRAPH_STATUS": _graph_status(context),
        "SEARCH_MATCHES": _graph_search_matches(context),
        "GRAPH_SVG": _graph_svg(context),
        "GRAPH_DETAILS": _graph_details(context),
        "RELATIONSHIP_COUNTS": _count_rows(context["relationship_counts"]),
        "SELECTED_ENTITY_INPUT": escape(selected.id, quote=True) if selected else "",
    }
    html = template
    for key, value in replacements.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def _count_rows(counts: dict[str, int]) -> str:
    return "\n".join(
        f'<div class="count-row"><span>{escape(label.replace("_", " ").title())}</span><strong>{count}</strong></div>'
        for label, count in counts.items()
    )


def _source_badges(sources: list[str]) -> str:
    if not sources:
        return '<span class="badge muted">N/A</span>'
    return "\n".join(
        f'<span class="badge">{escape(source)}</span>'
        for source in sources[:6]
    )


def _category_badges(categories: dict[str, int]) -> str:
    if not categories:
        return '<span class="badge muted">N/A</span>'
    return "\n".join(
        f'<span class="badge">{escape(category)} <small>{count}</small></span>'
        for category, count in categories.items()
    )


def _select_options(values: list[str], *, selected: str, empty_label: str) -> str:
    options = [f'<option value="">{escape(empty_label)}</option>']
    for value in values:
        selected_attr = " selected" if value == selected else ""
        label = value.replace("_", " ").title()
        options.append(
            f'<option value="{escape(value, quote=True)}"{selected_attr}>{escape(label)}</option>'
        )
    return "\n".join(options)


def _limit_options(selected: int) -> str:
    return "\n".join(
        f'<option value="{limit}"{" selected" if limit == selected else ""}>{limit}</option>'
        for limit in [25, 50, 100]
    )


def _depth_options(selected: int) -> str:
    return "\n".join(
        f'<option value="{depth}"{" selected" if depth == selected else ""}>Depth {depth}</option>'
        for depth in [1, 2]
    )


def _database_cards(rows: list[dict]) -> str:
    if not rows:
        return """
          <div class="empty">No matching entities found. Try a broader search or clear the current filters.</div>
        """
    return "\n".join(_database_card(row) for row in rows)


def _database_card(row: dict) -> str:
    entity = row["entity"]
    categories = entity.categories[:4]
    category_html = _entity_category_pills(categories)
    score = row["score"]
    score_html = f'<span class="score">score {score:.2f}</span>' if score is not None else ""
    description = entity.description or ""
    return f"""
          <article class="entity-card">
            <div class="card-top">
              <span class="type-badge">{escape(_humanize(str(entity.entity_type)))}</span>
              {score_html}
            </div>
            <h2>{escape(entity.name)}</h2>
            <p>{escape(description) if description else "No description available."}</p>
            <div class="pills">{category_html}</div>
            <dl>
              <div><dt>Provider</dt><dd>{escape(_provider_name(entity) or "N/A")}</dd></div>
              <div><dt>Relationships</dt><dd>{row["relationship_count"]}</dd></div>
            </dl>
            <div class="card-actions">
              <a href="/database/{escape(entity.id, quote=True)}">View Details</a>
              <a href="/entities/{escape(entity.id, quote=True)}">Raw JSON</a>
            </div>
          </article>
    """


def _active_filters(context: dict) -> str:
    filters = []
    if context["query"]:
        filters.append(f'Query: <strong>{escape(context["query"])}</strong>')
    if context["selected_type"]:
        filters.append(f'Type: <strong>{escape(context["selected_type"])}</strong>')
    if context["selected_category"]:
        filters.append(f'Category: <strong>{escape(context["selected_category"])}</strong>')
    if not filters:
        return "Showing the first records in the canonical dataset."
    return " · ".join(filters)


def _type_filter_links(context: dict) -> str:
    current = context["selected_type"]
    links = [_filter_link("/database", "All", current == "", {"q": context["query"], "category": context["selected_category"], "limit": context["limit"]})]
    for entity_type in context["entity_types"]:
        links.append(
            _filter_link(
                "/database",
                _humanize(entity_type),
                current == entity_type,
                {
                    "q": context["query"],
                    "type": entity_type,
                    "category": context["selected_category"],
                    "limit": context["limit"],
                },
            )
        )
    return "\n".join(links)


def _relationship_filter_links(context: dict) -> str:
    current = context["selected_type"]
    links = [_filter_link("/database/relationships", f"All {context['total_relationships']}", current == "", {"limit": context["limit"]})]
    for relationship_type, count in context["relationship_counts"].items():
        links.append(
            _filter_link(
                "/database/relationships",
                f"{_humanize(relationship_type)} {count}",
                current == relationship_type,
                {"relationship_type": relationship_type, "limit": context["limit"]},
            )
        )
    return "\n".join(links)


def _filter_link(path: str, label: str, active: bool, params: dict) -> str:
    href = _url(path, params)
    class_name = "filter active" if active else "filter"
    return f'<a class="{class_name}" href="{href}">{escape(label)}</a>'


def _pagination(path: str, *, page: int, total_pages: int, params: dict) -> str:
    if total_pages <= 1:
        return ""
    previous_link = (
        f'<a class="button" href="{_url(path, {**params, "page": page - 1})}">Previous</a>'
        if page > 1
        else '<span class="button disabled">Previous</span>'
    )
    next_link = (
        f'<a class="button" href="{_url(path, {**params, "page": page + 1})}">Next</a>'
        if page < total_pages
        else '<span class="button disabled">Next</span>'
    )
    return f'<nav class="pagination">{previous_link}<span>Page {page} of {total_pages}</span>{next_link}</nav>'


def _url(path: str, params: dict) -> str:
    clean = {
        key: value
        for key, value in params.items()
        if value not in [None, "", 0]
    }
    query = urlencode(clean)
    return f"{path}?{query}" if query else path


def _showing_range(context: dict, *, noun: str) -> str:
    if context["result_count"] == 0:
        return f"Showing 0 {noun}"
    return (
        f"Showing {context['start_index']}-{context['end_index']} "
        f"of {context['result_count']} {noun}"
    )


def _entity_category_pills(categories: list[str]) -> str:
    if not categories:
        return '<span class="muted">None</span>'
    return " ".join(f'<span class="pill">{escape(category)}</span>' for category in categories)


def _provider_name(entity) -> str | None:
    if entity.display and entity.display.provider_name:
        return entity.display.provider_name
    for field in ["provider", "company", "developer", "owner", "publisher"]:
        value = entity.metadata.get(field)
        if value:
            return str(value)
    return None


def _official_url(entity) -> str:
    if not entity.url:
        return '<span class="muted">N/A</span>'
    url = str(entity.url)
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{escape(url)}</a>'


def _source_rows(sources: list) -> str:
    if not sources:
        return '<p class="muted">No sources recorded.</p>'
    return "\n".join(
        f'<li><a href="{escape(str(source.url), quote=True)}" target="_blank" rel="noreferrer">{escape(source.name)}</a></li>'
        for source in sources
    )


def _metadata_rows(metadata: dict) -> str:
    if not metadata:
        return '<p class="muted">No specialized metadata recorded.</p>'
    rows = []
    for key, value in metadata.items():
        rows.append(
            f"<div><dt>{escape(_humanize(key))}</dt><dd>{escape(_format_value(value))}</dd></div>"
        )
    return "\n".join(rows)


def _relationship_view_cards(views: list) -> str:
    if not views:
        return '<p class="muted">No relationships in this direction.</p>'
    cards = []
    for view in views:
        related = view.related_entity
        related_name = related.name if related else view.relationship.target_id
        related_id = related.id if related else ""
        href = f"/database/{escape(related_id, quote=True)}" if related_id else "#"
        cards.append(
            f"""
            <article class="relationship-card">
              <span>{escape(_humanize(view.effective_relationship_type))}</span>
              <a href="{href}">{escape(related_name)}</a>
              <small>confidence {view.relationship.confidence:.2f}</small>
            </article>
            """
        )
    return "\n".join(cards)


def _relationship_explorer_rows(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">No relationships match this filter.</div>'
    cards = []
    for row in rows:
        relationship = row["relationship"]
        source = row["source"]
        target = row["target"]
        source_name = source.name if source else relationship.source_id
        target_name = target.name if target else relationship.target_id
        source_href = f"/database/{escape(source.id, quote=True)}" if source else "#"
        target_href = f"/database/{escape(target.id, quote=True)}" if target else "#"
        cards.append(
            f"""
            <article class="edge-card">
              <span class="type-badge">{escape(_humanize(str(relationship.relationship_type)))}</span>
              <div class="edge-flow">
                <a href="{source_href}">{escape(source_name)}</a>
                <strong>-></strong>
                <a href="{target_href}">{escape(target_name)}</a>
              </div>
              <small>confidence {relationship.confidence:.2f} · {len(relationship.evidence)} evidence records</small>
            </article>
            """
        )
    return "\n".join(cards)


def _graph_status(context: dict) -> str:
    selected = context["selected_entity"]
    if selected:
        return (
            f'Focused on <strong>{escape(selected.name)}</strong>: '
            f'{len(context["nodes"])} visible nodes and {len(context["edges"])} visible relationships.'
        )
    if context["query"]:
        return f'{len(context["matches"])} ranked entities found for <strong>{escape(context["query"])}</strong>.'
    return (
        f'{context["total_entities"]} entities available and '
        f'{context["total_relationships"]} relationships available. Search to render a focused graph.'
    )


def _graph_search_matches(context: dict) -> str:
    if context["selected_entity"]:
        return ""
    if not context["query"]:
        return """
          <div class="empty">Search for a company, tool, model, MCP server, device, repository, task, or other entity to explore its connections.</div>
        """
    if not context["matches"]:
        return '<div class="empty">No matching entities found. Try a broader search.</div>'
    cards = []
    for match in context["matches"]:
        entity = match.entity
        href = _url(
            "/graph",
            {
                "q": context["query"],
                "entity": entity.id,
                "depth": context["depth"],
                "type": context["selected_type"],
                "relationship_type": context["selected_relationship_type"],
            },
        )
        cards.append(
            f"""
            <article class="match-card">
              <span class="type-badge">{escape(_humanize(str(entity.entity_type)))}</span>
              <h3>{escape(entity.name)}</h3>
              <p>{escape(entity.description or "No description available.")}</p>
              <a href="{href}">Explore Graph</a>
            </article>
            """
        )
    return "\n".join(cards)


def _graph_svg(context: dict) -> str:
    nodes = context["nodes"]
    if not nodes:
        return '<div class="graph-empty">No graph selected yet.</div>'

    selected = context["selected_entity"]
    width = 920
    height = 560
    cx = width / 2
    cy = height / 2
    positions: dict[str, tuple[float, float]] = {}
    if selected:
        positions[selected.id] = (cx, cy)
    neighbors = [node for node in nodes if not selected or node.id != selected.id]
    for index, node in enumerate(neighbors):
        angle = (2 * math.pi * index) / max(len(neighbors), 1)
        radius = 190 if context["depth"] == 1 else 230
        positions[node.id] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

    edge_lines = []
    for edge in context["edges"]:
        relationship = edge["relationship"]
        source_pos = positions.get(relationship.source_id)
        target_pos = positions.get(relationship.target_id)
        if not source_pos or not target_pos:
            continue
        href = _url(
            "/graph",
            {
                "entity": selected.id if selected else relationship.source_id,
                "depth": context["depth"],
                "type": context["selected_type"],
                "relationship_type": context["selected_relationship_type"],
                "edge": relationship.id,
            },
        )
        edge_lines.append(
            f"""
            <a href="{href}">
              <line x1="{source_pos[0]:.1f}" y1="{source_pos[1]:.1f}" x2="{target_pos[0]:.1f}" y2="{target_pos[1]:.1f}" class="edge" />
              <title>{escape(_humanize(str(relationship.relationship_type)))} · Relationship Confidence {relationship.confidence:.2f}</title>
            </a>
            """
        )

    node_shapes = []
    for node in nodes:
        x, y = positions[node.id]
        href = _url(
            "/graph",
            {
                "entity": node.id,
                "depth": context["depth"],
                "type": context["selected_type"],
                "relationship_type": context["selected_relationship_type"],
            },
        )
        class_name = "node selected" if selected and node.id == selected.id else "node"
        label = _truncate(node.name, 18)
        node_shapes.append(
            f"""
            <a href="{href}">
              <g class="{class_name}">
                <circle cx="{x:.1f}" cy="{y:.1f}" r="34" />
                <text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle">{escape(label)}</text>
                <title>{escape(node.name)} · {escape(_humanize(str(node.entity_type)))}</title>
              </g>
            </a>
            """
        )

    return f"""
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="AI Orbit focused ecosystem graph">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#667085"></path>
          </marker>
        </defs>
        {"".join(edge_lines)}
        {"".join(node_shapes)}
      </svg>
    """


def _graph_details(context: dict) -> str:
    selected_edge = context["selected_edge"]
    selected = context["selected_entity"]
    if selected_edge:
        relationship = selected_edge["relationship"]
        source = selected_edge["source"]
        target = selected_edge["target"]
        return f"""
          <h2>Selected Relationship</h2>
          <p><strong>{escape(source.name if source else relationship.source_id)}</strong> -> <strong>{escape(target.name if target else relationship.target_id)}</strong></p>
          <dl>
            <div><dt>Type</dt><dd>{escape(_humanize(str(relationship.relationship_type)))}</dd></div>
            <div><dt>Relationship Confidence</dt><dd>{relationship.confidence:.2f}</dd></div>
            <div><dt>Evidence Records</dt><dd>{len(relationship.evidence)}</dd></div>
          </dl>
        """
    if selected:
        return f"""
          <h2>Selected Entity</h2>
          <p><strong>{escape(selected.name)}</strong></p>
          <dl>
            <div><dt>Type</dt><dd>{escape(_humanize(str(selected.entity_type)))}</dd></div>
            <div><dt>Visible Relationships</dt><dd>{len(context["edges"])}</dd></div>
          </dl>
          <a class="button primary" href="/database/{escape(selected.id, quote=True)}">View Database Record</a>
        """
    return """
      <h2>How To Explore</h2>
      <p>Search for an entity, choose a ranked canonical result, then click nodes or edges to inspect the graph neighborhood.</p>
      <a class="button" href="/stats">View Raw Statistics</a>
    """


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}..."


def _format_value(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


app = create_app()
