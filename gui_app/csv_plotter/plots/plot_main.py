import os
from dataclasses import dataclass

import pandas as pd

try:
    import datashader as ds
    import datashader.transfer_functions as tf
except Exception:
    ds = None
    tf = None

from matplotlib.figure import Figure
from matplotlib.lines import Line2D


@dataclass(frozen=True)
class MainPlotResult:
    fig: Figure
    axes_for_events: list
    stats_rows: list[tuple[str, str, str, str, str, str, str, str, str, str, str]]
    selected_columns: list[str]
    do_span: bool
    do_sync_xlim: bool


def build_main_plot(app, selector, subplot_index: int) -> MainPlotResult:
    selected_columns = selector.get_selected_columns(app.df.columns)
    stats_rows: list[tuple[str, str, str, str, str, str, str, str, str, str, str]] = []

    mode = selector.get_plot_mode()
    do_span = (mode == "Time series")
    do_sync_xlim = (mode in ("Time series", "AF-10047: Control vs Module"))

    active_col = getattr(selector, "_active_series", None)
    selected_data_cols = [c for c in selected_columns if c != "Timestamp" and c in app.df.columns]

    def _choose_from_selection(prefer: list[str]) -> str | None:
        if active_col and active_col in selected_data_cols:
            return active_col
        for pat in prefer:
            for c in selected_data_cols:
                if pat.lower() in str(c).lower():
                    return c
        return selected_data_cols[0] if selected_data_cols else None

    def _choose_other(exclude: set[str]) -> str | None:
        for c in selected_data_cols:
            if c not in exclude:
                return c
        return None

    fig = Figure(figsize=(8, 4), dpi=100)
    axes_for_events = []

    def _tag_line(line: Line2D, col_name: str | None) -> None:
        if col_name:
            try:
                line._csv_plotter_selector = selector
                line._csv_plotter_column = col_name
            except Exception:
                pass
        try:
            line.set_picker(True)
            line.set_pickradius(5)
        except Exception:
            pass

    def _make_legend_clickable(ax) -> None:
        """Make legend labels clickable so user can toggle series selection."""
        try:
            leg = ax.get_legend()
        except Exception:
            leg = None
        if leg is None:
            return
        try:
            texts = list(leg.get_texts() or [])
        except Exception:
            texts = []

        for txt in texts:
            try:
                label = str(txt.get_text() or "")
            except Exception:
                label = ""
            key = label
            if ":" in label:
                try:
                    key = label.split(":", 1)[1]
                except Exception:
                    key = label
            try:
                txt._csv_plotter_selector = selector
                txt._csv_plotter_column = str(key)
                txt._csv_plotter_action = "toggle_selection"
            except Exception:
                pass
            try:
                # tolerance in points
                txt.set_picker(5)
            except Exception:
                try:
                    txt.set_picker(True)
                except Exception:
                    pass

    if not selected_columns:
        ax = fig.add_subplot(111)
        axes_for_events = [ax]
        ax.set_title(f"Subplot {subplot_index + 1} (no selection)")
        selector.set_stats_text("")
        return MainPlotResult(
            fig=fig,
            axes_for_events=axes_for_events,
            stats_rows=stats_rows,
            selected_columns=selected_columns,
            do_span=do_span,
            do_sync_xlim=do_sync_xlim,
        )

    if "Timestamp" in app.df.columns:
        try:
            base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
        except Exception:
            base_path = ""
        try:
            x = app._to_numeric_cached(app.df, str(base_path), "Timestamp")
        except Exception:
            x = pd.to_numeric(app.df["Timestamp"], errors="coerce")
    else:
        x = pd.Series(range(len(app.df)))

    xwin = selector.get_x_window() if "Timestamp" in app.df.columns else None
    if xwin is not None:
        try:
            lo, hi = xwin
            mask = (x >= lo) & (x <= hi)
        except Exception:
            mask = None
    else:
        mask = None

    file_paths = []
    try:
        file_paths = selector.get_files()
    except Exception:
        file_paths = []

    if not file_paths:
        try:
            if isinstance(app.last_loaded_file, str) and app.last_loaded_file:
                file_paths = [app.last_loaded_file]
        except Exception:
            file_paths = []

    # Per-file overlay enable/disable (supports toggling base/source file too).
    try:
        if hasattr(selector, "is_file_enabled"):
            file_paths = [p for p in file_paths if bool(selector.is_file_enabled(str(p)))]
    except Exception:
        pass

    if mode == "Time series":
        ax = fig.add_subplot(111)
        axes_for_events = [ax]

        if not file_paths:
            ax.set_title("No enabled overlay files")
            ax.grid(True)
            selector.set_stats_text("")
            return MainPlotResult(
                fig=fig,
                axes_for_events=axes_for_events,
                stats_rows=stats_rows,
                selected_columns=selected_columns,
                do_span=do_span,
                do_sync_xlim=do_sync_xlim,
            )

        x_align = "aligned"
        try:
            x_align = selector.get_x_alignment_mode()
        except Exception:
            x_align = "aligned"

        try:
            shifts = selector.get_file_shifts()
        except Exception:
            shifts = {}

        multiple_files = len(file_paths) > 1
        xwin = selector.get_x_window()

        use_datashader = bool(getattr(app, "use_datashader", True))
        max_points = int(getattr(app, "datashader_threshold", 1_000_000))

        def _maybe_render_datashader(df_i: pd.DataFrame, x_raw, cols: list[str]) -> bool:
            if ds is None or tf is None or not use_datashader:
                return False
            try:
                if len(x_raw) < max_points:
                    return False
            except Exception:
                return False
            if not cols:
                return False
            try:
                data = pd.DataFrame({"x": x_raw})
                for c in cols:
                    data[c] = pd.to_numeric(df_i[c], errors="coerce")
                long_df = data.melt(id_vars=["x"], value_vars=cols, var_name="series", value_name="y").dropna()
                if long_df.empty:
                    return False
                color_key = {c: col for c, col in zip(cols, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"])}
                canvas = ds.Canvas(plot_width=1200, plot_height=400)
                agg = canvas.line(long_df, "x", "y", agg=ds.count_cat("series"))
                img = tf.shade(agg, color_key=color_key, how="eq_hist")
                pil = img.to_pil()
                ax.imshow(pil, extent=[long_df["x"].min(), long_df["x"].max(), long_df["y"].min(), long_df["y"].max()], aspect="auto")
                ax.set_title(f"Subplot {subplot_index + 1} (Datashader)")
                return True
            except Exception:
                return False

        for fp in file_paths:
            df_i, scale_i = app._get_df_for_path(str(fp), selector)
            if not isinstance(df_i, pd.DataFrame):
                continue

            if "Timestamp" in df_i.columns:
                try:
                    x_raw = app._to_numeric_cached(df_i, str(fp), "Timestamp")
                except Exception:
                    x_raw = pd.to_numeric(df_i["Timestamp"], errors="coerce")
            else:
                x_raw = pd.Series(range(len(df_i)))

            if len(file_paths) == 1:
                if _maybe_render_datashader(df_i, x_raw, selected_data_cols):
                    selector.set_stats_text("Datashader rasterized view")
                    return MainPlotResult(
                        fig=fig,
                        axes_for_events=axes_for_events,
                        stats_rows=stats_rows,
                        selected_columns=selected_columns,
                        do_span=do_span,
                        do_sync_xlim=do_sync_xlim,
                    )

            if x_align == "independent" and "Timestamp" in df_i.columns:
                try:
                    x0 = float(x_raw.dropna().iloc[0])
                except Exception:
                    x0 = 0.0
                x_plot = x_raw - x0
            else:
                x_plot = x_raw

            cfg = shifts.get(os.path.abspath(str(fp)), shifts.get(str(fp), {})) if isinstance(shifts, dict) else {}

            try:
                x_shift_s = float(cfg.get("x_shift_s", 0.0))
            except Exception:
                x_shift_s = 0.0

            try:
                denom = float(scale_i) if float(scale_i) != 0.0 else 1.0
            except Exception:
                denom = 1.0

            x_shift_units = float(x_shift_s) / denom
            try:
                x_plot = x_plot + x_shift_units
            except Exception:
                pass

            mask_i = None
            if xwin is not None:
                try:
                    lo, hi = xwin
                    mask_i = (x_plot >= float(lo)) & (x_plot <= float(hi))
                except Exception:
                    mask_i = None

            base_name = os.path.basename(str(fp))

            # Matplotlib becomes very slow / memory-hungry with huge lines.
            # Downsample plotted points to keep UI responsive.
            try:
                max_mpl_points = int(getattr(app, "mpl_max_points", 250_000) or 250_000)
            except Exception:
                max_mpl_points = 250_000

            for col in selected_columns:
                if col == "Timestamp":
                    continue
                if col not in df_i.columns:
                    continue

                try:
                    y = app._to_numeric_cached(df_i, str(fp), str(col))
                except Exception:
                    y = pd.to_numeric(df_i[col], errors="coerce")

                try:
                    y_shift = float(cfg.get("y_shift", 0.0))
                except Exception:
                    y_shift = 0.0

                if y_shift:
                    try:
                        y = y + float(y_shift)
                    except Exception:
                        pass

                # Downsample plot series when extremely large.
                try:
                    npts = int(len(y))
                except Exception:
                    npts = 0
                if max_mpl_points > 0 and npts > max_mpl_points:
                    try:
                        step = int((npts + max_mpl_points - 1) // max_mpl_points)
                    except Exception:
                        step = 1
                    if step > 1:
                        try:
                            x_plot_ds = x_plot.iloc[::step]
                            y_ds = y.iloc[::step]
                        except Exception:
                            x_plot_ds, y_ds = x_plot, y
                    else:
                        x_plot_ds, y_ds = x_plot, y
                else:
                    x_plot_ds, y_ds = x_plot, y

                y_stats = y
                x_stats = x_plot
                if mask_i is not None:
                    try:
                        y_masked = y.where(mask_i)
                        x_masked = x_plot.where(mask_i)
                        # If the window doesn't overlap the data at all,
                        # fall back to the full series so metrics aren't all n/a.
                        if y_masked.dropna().empty:
                            pass  # keep y_stats = y, x_stats = x_plot
                        else:
                            y_stats = y_masked
                            x_stats = x_masked
                    except Exception:
                        pass

                # Metrics need a time axis in seconds.
                # For fixed timebase, treat the trace as uniformly sampled (sample-index * dt),
                # even if a 'Timestamp' column exists (it may be a sample counter).
                x_metrics = x_stats
                try:
                    tb_mode = str(getattr(app, "_effective_timebase_mode_for_path")(str(fp), selector=selector) or "auto")
                except Exception:
                    tb_mode = "auto"

                if tb_mode == "fixed":
                    try:
                        import numpy as np

                        t = pd.Series(np.arange(len(df_i), dtype=float), index=df_i.index) * float(scale_i)
                    except Exception:
                        t = pd.Series(range(len(df_i)), index=df_i.index) * float(scale_i)
                    x_metrics = t
                    if mask_i is not None:
                        try:
                            x_metrics = x_metrics.where(mask_i)
                        except Exception:
                            pass
                else:
                    # Auto timebase: Timestamp axis scaled to seconds (if Timestamp exists).
                    if "Timestamp" in df_i.columns:
                        try:
                            x_metrics = x_stats * float(scale_i)
                        except Exception:
                            x_metrics = x_stats

                min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s = app._compute_signal_metrics_cached(
                    path=str(fp),
                    col=str(col),
                    x=x_metrics,
                    y=y_stats,
                    xwin=xwin,
                    x_align=str(x_align or ""),
                    x_shift_s=float(x_shift_s),
                    y_shift=float(y_shift),
                    scale_to_seconds=float(scale_i),
                )

                sig_name = str(col)
                if multiple_files:
                    sig_name = f"{base_name}:{col}"

                stats_rows.append((sig_name, min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s))

                ln, = ax.plot(x_plot_ds, y_ds, label=sig_name)
                _tag_line(ln, str(col))

        # Keep the axis zoomed to the analysis window across replots.
        # (The window is set via span-select and/or toolbar zoom.)
        try:
            xwin_apply = selector.get_x_window()
        except Exception:
            xwin_apply = None
        if xwin_apply is not None:
            try:
                lo, hi = xwin_apply
                ax.set_xlim(float(lo), float(hi))
            except Exception:
                pass
        else:
            # If there is no persisted window, ensure X autoscale is enabled.
            # Matplotlib zoom/pan can leave the axis in manual-limits mode.
            try:
                ax.relim()
            except Exception:
                pass
            try:
                ax.autoscale(enable=True, axis="x")
            except Exception:
                pass
            try:
                ax.autoscale_view()
            except Exception:
                pass

        selector.set_stats_text("")
        ax.set_title(f"Subplot {subplot_index + 1}")
        ax.grid(True)

        labels = [line.get_label() for line in ax.get_lines()]
        n = len(labels)
        if n:
            if n <= 10:
                legend_font = 9
                ncol = 1
            elif n <= 20:
                legend_font = 8
                ncol = 1
            else:
                legend_font = 7
                ncol = 2
            fig.subplots_adjust(right=0.72)
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=legend_font,
                ncol=ncol,
                frameon=True,
            )
            _make_legend_clickable(ax)

        ylim_cfg = selector.get_ylim_config()
        if isinstance(ylim_cfg, dict) and bool(ylim_cfg.get("enabled")):
            ymin_raw = str(ylim_cfg.get("ymin", "")).strip()
            ymax_raw = str(ylim_cfg.get("ymax", "")).strip()
            ymin = None
            ymax = None
            if ymin_raw:
                try:
                    ymin = float(ymin_raw)
                except Exception:
                    ymin = None
            if ymax_raw:
                try:
                    ymax = float(ymax_raw)
                except Exception:
                    ymax = None
            if ymin is not None or ymax is not None:
                try:
                    ax.set_ylim(bottom=ymin, top=ymax)
                except Exception:
                    pass

    elif mode == "MS-1353: Tube temperature":
        ax = fig.add_subplot(111)
        axes_for_events = [ax]

        tube_col = _choose_from_selection(["temptube", "tube"])
        if tube_col and tube_col in app.df.columns:
            try:
                base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
            except Exception:
                base_path = ""
            try:
                y = app._to_numeric_cached(app.df, str(base_path), str(tube_col))
            except Exception:
                y = pd.to_numeric(app.df[tube_col], errors="coerce")
            y_stats = y
            x_stats = x
            if mask is not None:
                try:
                    y_masked = y.where(mask)
                    x_masked = x.where(mask)
                    if y_masked.dropna().empty:
                        pass  # window doesn't overlap data; use full series
                    else:
                        y_stats = y_masked
                        x_stats = x_masked
                except Exception:
                    pass

            try:
                _df_tmp, eff_scale = app._get_df_for_path(str(base_path), selector)
            except Exception:
                eff_scale = float(getattr(app, "_timestamp_scale_to_seconds", 1.0) or 1.0)

            x_metrics = x_stats
            try:
                tb_mode = str(getattr(app, "_effective_timebase_mode_for_path")(str(base_path), selector=selector) or "auto")
            except Exception:
                tb_mode = "auto"

            if tb_mode == "fixed":
                try:
                    import numpy as np

                    t = pd.Series(np.arange(len(app.df), dtype=float), index=app.df.index) * float(eff_scale)
                except Exception:
                    t = pd.Series(range(len(app.df)), index=app.df.index) * float(eff_scale)
                x_metrics = t
                if mask is not None:
                    try:
                        x_metrics = x_metrics.where(mask)
                    except Exception:
                        pass
            else:
                try:
                    x_metrics = x_stats * float(eff_scale)
                except Exception:
                    x_metrics = x_stats

            min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s = app._compute_signal_metrics_cached(
                path=str(base_path),
                col=str(tube_col),
                x=x_metrics,
                y=y_stats,
                xwin=selector.get_x_window(),
                x_align=str(getattr(selector, "get_x_alignment_mode", lambda: "aligned")() or ""),
                x_shift_s=0.0,
                y_shift=0.0,
                    scale_to_seconds=float(eff_scale or 1.0),
            )
            stats_rows.append((str(tube_col), min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s))

            ln, = ax.plot(x, y, label=str(tube_col))
            _tag_line(ln, tube_col)
            ax.legend(loc="best")
            _make_legend_clickable(ax)
            ax.set_title("MS-1353 tube temperature")
        else:
            ax.set_title("MS-1353 tube temperature (missing tube column)")

        ax.grid(True)

        ylim_cfg = selector.get_ylim_config()
        if isinstance(ylim_cfg, dict) and bool(ylim_cfg.get("enabled")):
            ymin_raw = str(ylim_cfg.get("ymin", "")).strip()
            ymax_raw = str(ylim_cfg.get("ymax", "")).strip()
            ymin = None
            ymax = None
            if ymin_raw:
                try:
                    ymin = float(ymin_raw)
                except Exception:
                    ymin = None
            if ymax_raw:
                try:
                    ymax = float(ymax_raw)
                except Exception:
                    ymax = None
            if ymin is not None or ymax is not None:
                try:
                    ax.set_ylim(bottom=ymin, top=ymax)
                except Exception:
                    pass

    elif mode == "MS-1353: Range/Diff":
        tube_col = _choose_from_selection(["temptube", "tube"])
        det_cols = [c for c in selected_data_cols if c != tube_col]

        if len(det_cols) < 2:
            ax = fig.add_subplot(111)
            axes_for_events = [ax]
            ax.set_title("MS-1353 Range/Diff (select 2+ detector columns)")
            ax.grid(True)
        else:
            fig.set_size_inches(12, 7)
            ax1 = fig.add_subplot(3, 1, 1)
            ax2 = fig.add_subplot(3, 1, 2)
            ax3 = fig.add_subplot(3, 1, 3)
            axes_for_events = [ax1, ax2, ax3]

            det = app.df[det_cols].apply(pd.to_numeric, errors="coerce")
            det_min = det.min(axis=1)
            det_max = det.max(axis=1)
            det_diff = det_max - det_min

            try:
                import numpy as np

                idx = np.arange(len(det_min))
            except Exception:
                idx = list(range(len(det_min)))

            rmin, rmax, dmax = app._ms1353_limits(len(det_min))

            if rmin is not None:
                ax1.plot(idx, det_min, ".-", label="min")
                ax1.plot(idx, det_max, ".-", label="max")
                ax1.plot(idx, rmin, "r--", label="min limit")
                ax1.plot(idx, rmax, "r--", label="max limit")
                ax1.set_title("Temperature abs range")
                ax1.grid(True, which="both")
                ax1.legend(loc="best")
                _make_legend_clickable(ax1)

                ax2.plot(idx, det_diff, ".-", label="max-min")
                ax2.plot(idx, dmax, "r--", label="diff limit")
                ax2.set_title("Temperature relative difference")
                ax2.grid(True, which="both")
                ax2.legend(loc="best")
                _make_legend_clickable(ax2)

                if tube_col and tube_col in app.df.columns:
                    try:
                        base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                    except Exception:
                        base_path = ""
                    try:
                        tube = app._to_numeric_cached(app.df, str(base_path), str(tube_col))
                    except Exception:
                        tube = pd.to_numeric(app.df[tube_col], errors="coerce")
                    tube_diff = tube.diff().fillna(0)
                    inc = tube_diff > 0
                    det_diff_xray = det_diff.where(inc)
                    ax3.plot(idx, det_diff_xray, ".-", label="scan diff")
                    ax3.plot(idx, dmax, "r--", label="diff limit")
                    ax3.set_title("Difference during scans (tube increasing)")
                    ax3.grid(True, which="both")
                    ax3.legend(loc="best")
                    _make_legend_clickable(ax3)
                else:
                    ax3.set_title("Difference during scans (select a tube series to enable scan mask)")
                    ax3.grid(True, which="both")
            else:
                ax1.set_title("MS-1353 Range/Diff (failed to build limits)")

            for col in det_cols:
                try:
                    base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                except Exception:
                    base_path = ""
                try:
                    _df_tmp, eff_scale = app._get_df_for_path(str(base_path), selector)
                except Exception:
                    eff_scale = float(getattr(app, "_timestamp_scale_to_seconds", 1.0) or 1.0)
                try:
                    y = app._to_numeric_cached(app.df, str(base_path), str(col))
                except Exception:
                    y = pd.to_numeric(app.df[col], errors="coerce")
                y_stats = y
                x_stats = x
                if mask is not None:
                    try:
                        y_masked = y.where(mask)
                        x_masked = x.where(mask)
                        if y_masked.dropna().empty:
                            pass  # window doesn't overlap data; use full series
                        else:
                            y_stats = y_masked
                            x_stats = x_masked
                    except Exception:
                        pass

                x_metrics = x_stats
                try:
                    tb_mode = str(getattr(app, "_effective_timebase_mode_for_path")(str(base_path), selector=selector) or "auto")
                except Exception:
                    tb_mode = "auto"
                if tb_mode == "fixed":
                    try:
                        import numpy as np

                        t = pd.Series(np.arange(len(app.df), dtype=float), index=app.df.index) * float(eff_scale)
                    except Exception:
                        t = pd.Series(range(len(app.df)), index=app.df.index) * float(eff_scale)
                    x_metrics = t
                    if mask is not None:
                        try:
                            x_metrics = x_metrics.where(mask)
                        except Exception:
                            pass
                else:
                    try:
                        x_metrics = x_stats * float(eff_scale)
                    except Exception:
                        x_metrics = x_stats

                min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s = app._compute_signal_metrics_cached(
                    path=str(base_path),
                    col=str(col),
                    x=x_metrics,
                    y=y_stats,
                    xwin=selector.get_x_window(),
                    x_align=str(getattr(selector, "get_x_alignment_mode", lambda: "aligned")() or ""),
                    x_shift_s=0.0,
                    y_shift=0.0,
                    scale_to_seconds=float(eff_scale or 1.0),
                )
                stats_rows.append((str(col), min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s))

    else:
        candidate_cols = selected_data_cols
        module_col = _choose_from_selection(["detmiddle", "module", "modulet", "pv", "tempdetmiddle"]) or (
            candidate_cols[0] if candidate_cols else None
        )
        control_col = _choose_other({module_col} if module_col else set())

        trigger_col = None
        if mode in ("AF-10047: ACQ ON", "AF-10047: ACQ OFF"):
            trigger_col = _choose_from_selection(["acq", "state", "trigger", "on", "off"])
            if trigger_col in {module_col, control_col}:
                trigger_col = _choose_other({module_col, control_col} - {None})

        x_sec = x
        if "Timestamp" in app.df.columns:
            try:
                base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                ts = app._to_numeric_cached(app.df, str(base_path), "Timestamp")
                try:
                    _df_tmp, eff_scale = app._get_df_for_path(str(base_path), selector)
                except Exception:
                    eff_scale = float(getattr(app, "_timestamp_scale_to_seconds", 1.0) or 1.0)

                try:
                    tb_mode = str(getattr(app, "_effective_timebase_mode_for_path")(str(base_path), selector=selector) or "auto")
                except Exception:
                    tb_mode = "auto"

                if tb_mode == "fixed":
                    try:
                        import numpy as np

                        x_sec = pd.Series(np.arange(len(app.df), dtype=float), index=app.df.index) * float(eff_scale)
                    except Exception:
                        x_sec = pd.Series(range(len(app.df)), index=app.df.index) * float(eff_scale)
                else:
                    x_sec = (ts - float(ts.iloc[0])) * float(eff_scale)
            except Exception:
                x_sec = pd.to_numeric(app.df["Timestamp"], errors="coerce")

        range_plus_pct = 0.0125

        if mode == "AF-10047: Control vs Module":
            ax = fig.add_subplot(111)
            axes_for_events = [ax]

            if module_col and control_col and module_col in app.df.columns and control_col in app.df.columns:
                try:
                    base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                except Exception:
                    base_path = ""
                try:
                    y_ctrl = app._to_numeric_cached(app.df, str(base_path), str(control_col))
                except Exception:
                    y_ctrl = pd.to_numeric(app.df[control_col], errors="coerce")
                try:
                    y_mod = app._to_numeric_cached(app.df, str(base_path), str(module_col))
                except Exception:
                    y_mod = pd.to_numeric(app.df[module_col], errors="coerce")

                try:
                    ctrl_min = float(y_ctrl.dropna().min())
                    ctrl_max = float(y_ctrl.dropna().max())
                    mod_min = float(y_mod.dropna().min())
                    mod_max = float(y_mod.dropna().max())
                except Exception:
                    ctrl_min = ctrl_max = mod_min = mod_max = 0.0

                looks_percent = (0 <= ctrl_min <= 5) and (0 <= ctrl_max <= 120) and (mod_max - mod_min > 1.0)

                if looks_percent:
                    ax2y = ax.twinx()
                    ax.plot(x_sec, y_mod, label=str(module_col), color="tab:blue")
                    ax2y.plot(x_sec, y_ctrl, label=str(control_col), color="tab:orange", alpha=0.8)
                    ax.set_ylabel("C")
                    ax2y.set_ylabel("%")

                    lines = ax.get_lines() + ax2y.get_lines()
                    labels = [l.get_label() for l in lines]
                    ax.legend(lines, labels, loc="best")
                    _make_legend_clickable(ax)
                else:
                    ax.plot(x_sec, y_ctrl, label=str(control_col))
                    ax.plot(x_sec, y_mod, label=str(module_col))
                    ax.legend(loc="best")
                    _make_legend_clickable(ax)

                ax.set_title("AF-10047 Control vs Module temperature")
                ax.set_xlabel("sec")
                ax.grid(True)
            else:
                ax.set_title("AF-10047 Control vs Module (missing columns)")
                ax.grid(True)

            for col in candidate_cols:
                try:
                    base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                except Exception:
                    base_path = ""
                try:
                    _df_tmp, eff_scale = app._get_df_for_path(str(base_path), selector)
                except Exception:
                    eff_scale = float(getattr(app, "_timestamp_scale_to_seconds", 1.0) or 1.0)
                try:
                    y = app._to_numeric_cached(app.df, str(base_path), str(col))
                except Exception:
                    y = pd.to_numeric(app.df[col], errors="coerce")
                y_stats = y
                x_stats = x
                if mask is not None:
                    try:
                        y_masked = y.where(mask)
                        x_masked = x.where(mask)
                        if y_masked.dropna().empty:
                            pass  # window doesn't overlap data; use full series
                        else:
                            y_stats = y_masked
                            x_stats = x_masked
                    except Exception:
                        pass
                x_metrics = x_stats
                try:
                    tb_mode = str(getattr(app, "_effective_timebase_mode_for_path")(str(base_path), selector=selector) or "auto")
                except Exception:
                    tb_mode = "auto"
                if tb_mode == "fixed":
                    try:
                        import numpy as np

                        t = pd.Series(np.arange(len(app.df), dtype=float), index=app.df.index) * float(eff_scale)
                    except Exception:
                        t = pd.Series(range(len(app.df)), index=app.df.index) * float(eff_scale)
                    x_metrics = t
                    if mask is not None:
                        try:
                            x_metrics = x_metrics.where(mask)
                        except Exception:
                            pass
                else:
                    try:
                        x_metrics = x_stats * float(eff_scale)
                    except Exception:
                        x_metrics = x_stats

                min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s = app._compute_signal_metrics_cached(
                    path=str(base_path),
                    col=str(col),
                    x=x_metrics,
                    y=y_stats,
                    xwin=selector.get_x_window(),
                    x_align=str(getattr(selector, "get_x_alignment_mode", lambda: "aligned")() or ""),
                    x_shift_s=0.0,
                    y_shift=0.0,
                    scale_to_seconds=float(eff_scale or 1.0),
                )
                stats_rows.append((str(col), min_s, max_s, avg_s, med_s, p2p_s, std_s, rms_s, crest_s, freq_s, period_s))

        elif mode in ("AF-10047: ACQ ON", "AF-10047: ACQ OFF"):
            fig.set_size_inches(12, 7)
            ax1 = fig.add_subplot(2, 1, 1)
            ax2 = fig.add_subplot(2, 1, 2)
            axes_for_events = [ax1, ax2]

            if (
                module_col
                and control_col
                and trigger_col
                and module_col in app.df.columns
                and control_col in app.df.columns
                and trigger_col in app.df.columns
            ):
                try:
                    base_path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
                except Exception:
                    base_path = ""
                try:
                    y_ctrl = app._to_numeric_cached(app.df, str(base_path), str(control_col))
                except Exception:
                    y_ctrl = pd.to_numeric(app.df[control_col], errors="coerce")
                try:
                    y_mod = app._to_numeric_cached(app.df, str(base_path), str(module_col))
                except Exception:
                    y_mod = pd.to_numeric(app.df[module_col], errors="coerce")
                try:
                    y_trig = app._to_numeric_cached(app.df, str(base_path), str(trigger_col)).fillna(0)
                except Exception:
                    y_trig = pd.to_numeric(app.df[trigger_col], errors="coerce").fillna(0)
                title = "ACQ ON" if mode.endswith("ON") else "ACQ OFF"

                try:
                    thr = 0.5
                    trig = (y_trig > thr).astype(int)
                    d = trig.diff().fillna(0)
                    if mode.endswith("ON"):
                        edge_idx = list(d[d > 0].index)
                    else:
                        edge_idx = list(d[d < 0].index)
                except Exception:
                    edge_idx = []

                edge_idx = edge_idx[:5]

                try:
                    dt = float(pd.to_numeric(x_sec, errors="coerce").diff().dropna().median())
                    if not dt or dt <= 0:
                        dt = 1.0
                except Exception:
                    dt = 1.0

                for k in edge_idx:
                    end_k = min(int(k) + 110, len(app.df))
                    seg_x = pd.Series(range(end_k - int(k))) * dt
                    ax1.plot(seg_x, y_ctrl.iloc[int(k):end_k], label=f"idx {int(k)}")
                    ax2.plot(seg_x, y_mod.iloc[int(k):end_k], label=f"idx {int(k)}")

                try:
                    base = float(y_mod.dropna().median())
                    a = base * (1 + range_plus_pct / 100.0)
                    b = base * (1 - range_plus_pct / 100.0)
                    ax2.plot([0, 110 * dt], [a, a], "r--")
                    ax2.plot([0, 110 * dt], [b, b], "r--")
                except Exception:
                    pass

                ax1.set_title(f"| -> {title} | Cool PID control output")
                ax1.set_ylabel("%")
                ax1.set_xlabel("sec")
                ax1.grid(True)
                ax2.set_title(f"| -> {title} | Module ({module_col})")
                ax2.set_ylabel("C")
                ax2.set_xlabel("sec")
                ax2.grid(True)
                ax1.legend(loc="best")
                _make_legend_clickable(ax1)
                ax2.legend(loc="best")
                _make_legend_clickable(ax2)
            else:
                ax1.set_title("AF-10047 ACQ plot (select module + control + trigger series)")
                ax1.grid(True)
                ax2.grid(True)

    return MainPlotResult(
        fig=fig,
        axes_for_events=axes_for_events,
        stats_rows=stats_rows,
        selected_columns=selected_columns,
        do_span=do_span,
        do_sync_xlim=do_sync_xlim,
    )
