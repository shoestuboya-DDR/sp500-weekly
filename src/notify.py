"""通知判定・メール組み立て・送信。"""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from weekly import WeekPoint

ERROR_NOTIFY_INTERVAL = timedelta(hours=24)


@dataclass(frozen=True)
class Mail:
    subject: str
    text: str
    html: str


# ---------------------------------------------------------------- 判定（純粋関数）


def decide_weekly_mail(
    weeks: list[WeekPoint],
    last_notified_week: str | None,
    *,
    weekly_summary: bool,
    fund_name: str,
    site_url: str,
) -> tuple[WeekPoint | None, Mail | None]:
    """通知対象の確定週と、送るメールを返す。

    戻り値の週は「通知済み」として記録すべき週（メールを送らない場合も含む）。
    何もしなくていいときは (None, None)。
    """
    confirmed = next((w for w in weeks if not w.is_partial), None)
    if confirmed is None:
        return None, None
    if last_notified_week is not None and confirmed.week <= last_notified_week:
        return None, None
    if confirmed.change_pct is None:
        return confirmed, None
    if confirmed.alert or weekly_summary:
        return confirmed, build_week_mail(confirmed, fund_name, site_url)
    return confirmed, None


def should_send_error(last_error_notified_at: str | None, now: datetime) -> bool:
    if not last_error_notified_at:
        return True
    return now - datetime.fromisoformat(last_error_notified_at) >= ERROR_NOTIFY_INTERVAL


# ---------------------------------------------------------------- メール組み立て


def _md(d: date) -> str:
    return f"{d.month}/{d.day}"


def _yen(p: int) -> str:
    return f"{p:,}円"


def _pct(x: float) -> str:
    return f"{x:+.2f}%"


def build_week_mail(w: WeekPoint, fund_name: str, site_url: str) -> Mail:
    assert w.change_pct is not None and w.prev_date is not None and w.prev_price is not None
    arrow = "▲" if w.change_pct >= 0 else "▼"
    if w.alert:
        subject = f"🚨【アラート】[S&P500] {w.week} 前週比 {_pct(w.change_pct)} {_yen(w.price)}"
        title = "🚨【アラート】S&P500 が前週比 −5% 以上下落"
    else:
        subject = f"[S&P500] {w.week} 前週比 {_pct(w.change_pct)} {_yen(w.price)}"
        title = f"📈 S&P500 週末チェック（{w.week}）"

    lines = [
        title,
        f"今週末 {_md(w.date)}: {_yen(w.price)}",
        f"前週末 {_md(w.prev_date)}: {_yen(w.prev_price)}",
        f"前週比: {_pct(w.change_pct)} {arrow}",
        "",
        f"ファンド: {fund_name}",
    ]
    if site_url:
        lines.append(site_url)
    text = "\n".join(lines) + "\n"

    color = "#c62828" if w.change_pct < 0 else "#2e7d32"
    pct_style = f"color:{color};font-size:1.6em;"
    if w.alert:
        pct_style += "font-weight:bold;"
    banner = (
        '<div style="background:#c62828;color:#fff;padding:12px 16px;font-weight:bold;'
        'border-radius:6px;margin-bottom:12px;">⚠ 前週比 −5% 以上の下落</div>'
        if w.alert
        else ""
    )
    link = (
        f'<p><a href="{html.escape(site_url)}">サイトで推移を見る</a></p>' if site_url else ""
    )
    body_html = f"""<div style="font-family:sans-serif;line-height:1.6;">
{banner}<h2 style="margin:0 0 8px;">S&amp;P500 週末チェック（{html.escape(w.week)}）</h2>
<table style="border-collapse:collapse;">
<tr><td style="padding:2px 12px 2px 0;">今週末 {_md(w.date)}</td><td><b>{_yen(w.price)}</b></td></tr>
<tr><td style="padding:2px 12px 2px 0;">前週末 {_md(w.prev_date)}</td><td>{_yen(w.prev_price)}</td></tr>
</table>
<p style="{pct_style}">前週比 {_pct(w.change_pct)} {arrow}</p>
<p style="color:#666;font-size:0.9em;">{html.escape(fund_name)}</p>
{link}</div>"""
    return Mail(subject=subject, text=text, html=body_html)


def build_error_mail(message: str, latest_date: str | None) -> Mail:
    subject = "⚠【エラー】[S&P500] データ取得に失敗"
    text = (
        "⚠ S&P500 週末チェック：データ取得に失敗\n"
        f"内容: {message}\n"
        f"最終取得データ: {latest_date or '不明'}\n"
    )
    body_html = (
        '<div style="font-family:sans-serif;line-height:1.6;">'
        '<p style="color:#b26a00;font-weight:bold;">⚠ S&amp;P500 週末チェック：データ取得に失敗</p>'
        f"<p>内容: {html.escape(message)}<br>最終取得データ: {html.escape(latest_date or '不明')}</p>"
        "</div>"
    )
    return Mail(subject=subject, text=text, html=body_html)


# ---------------------------------------------------------------- 送信


class GmailSender:
    HOST = "smtp.gmail.com"
    PORT = 465

    def __init__(self, user: str, app_password: str, to: list[str]):
        self.user = user
        self.app_password = app_password
        self.to = to

    def send(self, mail: Mail) -> None:
        msg = EmailMessage()
        msg["Subject"] = mail.subject
        msg["From"] = self.user
        msg["To"] = ", ".join(self.to)
        msg.set_content(mail.text)
        msg.add_alternative(mail.html, subtype="html")
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.HOST, self.PORT, context=ctx, timeout=30) as smtp:
            smtp.login(self.user, self.app_password)
            smtp.send_message(msg)


class ConsoleSender:
    """送信せずに標準出力へ表示する（ローカル確認・dry-run 用）。"""

    def send(self, mail: Mail) -> None:
        print("=" * 60)
        print(f"[DRY-RUN] Subject: {mail.subject}")
        print("-" * 60)
        print(mail.text)


def sender_from_env() -> GmailSender | None:
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    to = [a.strip() for a in os.environ.get("MAIL_TO", "").split(",") if a.strip()]
    if not (user and password and to):
        return None
    return GmailSender(user, password, to)
