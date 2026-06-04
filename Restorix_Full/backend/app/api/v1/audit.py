import csv
import io
import json as _json
from datetime import datetime
from typing import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogOut, AuditListResponse


router = APIRouter()

MAX_PAGE_SIZE = 500
MAX_CSV_ROWS = 50000


def _parse_meta(raw):
    if not raw:
        return '', {}
    try:
        meta = _json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return '', {'_raw': str(raw)}
    if not isinstance(meta, dict):
        return '', {}
    return (meta.get('description', '') or ''), meta


def _serialize(row: AuditLog, email: str | None) -> AuditLogOut:
    description, meta = _parse_meta(row.metadata_json)
    return AuditLogOut(
        id=row.id,
        org_id=row.org_id,
        user_id=row.user_id,
        user_email=email,
        action=row.action,
        target_type=row.target_type,
        target_id=str(row.target_id) if row.target_id else None,
        description=description,
        metadata=meta,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        created_at=row.created_at,
    )


def _build_filters(stmt, *, org_filter, from_, to, user_id, action, q):
    if org_filter is not None:
        stmt = stmt.where(AuditLog.org_id == org_filter)
    if from_ is not None:
        stmt = stmt.where(AuditLog.created_at >= from_)
    if to is not None:
        stmt = stmt.where(AuditLog.created_at <= to)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if q:
        q_escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f'%{q_escaped}%'
        stmt = stmt.where(or_(
            AuditLog.metadata_json.ilike(like, escape="\\"),
            AuditLog.action.ilike(like, escape="\\"),
        ))
    return stmt


def _require_audit_role(current_user: User):
    role = current_user.role
    role_val = role.value if hasattr(role, 'value') else str(role)
    if role_val == 'superadmin':
        return None
    if role_val == 'admin':
        return current_user.org_id
    raise HTTPException(403, 'Forbidden')


async def _email_map(db: AsyncSession, rows):
    ids = {r.user_id for r in rows if r.user_id is not None}
    if not ids:
        return {}
    res = await db.execute(select(User.id, User.email).where(User.id.in_(ids)))
    return {uid: em for uid, em in res.all()}


@router.get('/', response_model=AuditListResponse)
async def list_audit_logs(
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    user_id: UUID | None = None,
    action: str | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_filter = _require_audit_role(current_user)

    base = _build_filters(select(AuditLog), org_filter=org_filter, from_=from_, to=to,
                          user_id=user_id, action=action, q=q)
    count_q = _build_filters(select(func.count()).select_from(AuditLog), org_filter=org_filter,
                             from_=from_, to=to, user_id=user_id, action=action, q=q)
    total = (await db.execute(count_q)).scalar_one()

    items_q = base.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(items_q)).scalars().all()
    emails = await _email_map(db, rows)
    items = [_serialize(r, emails.get(r.user_id)) for r in rows]
    return AuditListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get('/export.csv')
async def export_csv(
    from_: datetime | None = Query(default=None, alias='from'),
    to: datetime | None = None,
    user_id: UUID | None = None,
    action: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_filter = _require_audit_role(current_user)

    base = _build_filters(select(AuditLog), org_filter=org_filter, from_=from_, to=to,
                          user_id=user_id, action=action, q=q)
    base = base.order_by(AuditLog.created_at.desc()).limit(MAX_CSV_ROWS + 1)
    rows = (await db.execute(base)).scalars().all()
    truncated = len(rows) > MAX_CSV_ROWS
    rows = rows[:MAX_CSV_ROWS]
    emails = await _email_map(db, rows)

    async def _generate() -> AsyncIterator[bytes]:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['created_at', 'user_email', 'action', 'target_type', 'target_id',
                         'description', 'ip_address', 'metadata_json'])
        yield buf.getvalue().encode('utf-8')
        buf.seek(0); buf.truncate(0)
        for r in rows:
            ser = _serialize(r, emails.get(r.user_id))
            writer.writerow([
                ser.created_at.isoformat(),
                ser.user_email or '',
                ser.action,
                ser.target_type or '',
                ser.target_id or '',
                ser.description or '',
                ser.ip_address or '',
                _json.dumps(ser.metadata, ensure_ascii=False),
            ])
            yield buf.getvalue().encode('utf-8')
            buf.seek(0); buf.truncate(0)

    headers = {'Content-Disposition': 'attachment; filename="audit.csv"'}
    if truncated:
        headers['X-Truncated'] = 'true'
    return StreamingResponse(_generate(), media_type='text/csv', headers=headers)
