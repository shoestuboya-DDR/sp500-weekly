"""基準価額 CSV のダウンロードとデコード。"""

from __future__ import annotations

import time
import urllib.request

USER_AGENT = "sp500-weekly-checker/1.0 (+personal use)"


def decode_csv(raw: bytes) -> str:
    """CSV のバイト列を文字列にする。

    投信協会の CSV は Content-Type が utf-8 でも中身は Shift_JIS(CP932) なので、
    UTF-8 として読めなければ CP932 で読む。
    """
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp932")


def fetch_csv(url: str, *, timeout: float = 30.0, retries: int = 3, wait: float = 5.0) -> str:
    """URL から CSV を取得して文字列で返す。失敗時は retries 回まで再試行する。"""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return decode_csv(res.read())
        except Exception as e:  # noqa: BLE001 - ネットワーク系の例外はまとめて再試行する
            last_error = e
            if attempt < retries:
                time.sleep(wait)
    raise RuntimeError(f"CSV のダウンロードに失敗（{retries}回試行）: {last_error}")
