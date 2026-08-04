from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st


def option_map(items, label_fn=lambda x: str(x)) -> tuple[list[int], dict[int, str]]:
    ids = [item.id for item in items]
    labels = {item.id: label_fn(item) for item in items}
    return ids, labels


def match_label(match) -> str:
    score = ""
    if match.home_score is not None and match.away_score is not None:
        score = f" · {match.home_score}-{match.away_score}"
    return f"{match.match_date.strftime('%d/%m/%Y')} · {match.round_name} · {match.home_team.name} - {match.away_team.name}{score}"


def report_label(report) -> str:
    return f"{report.match.round_name} · {report.match.home_team.name} - {report.match.away_team.name} · {report.reporter.full_name}"


def show_errors(errors: list[str]) -> None:
    for error in errors:
        st.error(error)


def dataframe_download(df: pd.DataFrame, filename: str, label: str = "Descargar CSV") -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv")
