import time
import tkinter as tk

from .config import BREAK_MIN, DISPLAY_SIZES, FOCUS_MIN, PETS, WELLNESS_MIN
from .platforms import STARTUP_LABEL
from .util import fmt_duration

TOGGLES = (("Chase my cursor", "chase"), ("Gravity", "gravity"), (f"Wellness nudges (every {WELLNESS_MIN} min)", "wellness"),
           ("Sounds", "sound"))


def build_menu(app):
    menu = tk.Menu(app.root, tearoff=0)
    app.pet_menu, app.reminder_menu, app.focus_menu = (tk.Menu(menu, tearoff=0) for _ in range(3))
    for key in PETS:
        app.pet_menu.add_radiobutton(label=key, variable=app.pet_var, value=key, command=app.switch_pet)
    app.pet_menu.add_separator()
    app.pet_menu.add_command(label="Invite a friend over")
    menu.add_cascade(label="Pet", menu=app.pet_menu)
    menu.add_command(label="Feed a treat", command=app.feed)
    menu.add_command(label="Show stats", command=app.show_stats)
    menu.add_command(label="Put on a show!", command=app.toggle_show)
    app.show_index = menu.index("end")
    menu.add_separator()
    menu.add_command(label="Set reminder...", command=app.open_reminder_dialog)
    menu.add_cascade(label="Active reminders", menu=app.reminder_menu)
    app.reminder_index = menu.index("end")
    menu.add_cascade(label="Focus timer", menu=app.focus_menu)
    menu.add_separator()
    for label, name in TOGGLES:
        menu.add_checkbutton(label=label, variable=app.flags[name], command=app.on_toggle)
    size_menu = tk.Menu(menu, tearoff=0)
    for size in DISPLAY_SIZES:
        size_menu.add_radiobutton(label=size, variable=app.size_var, value=size, command=app.set_size)
    menu.add_cascade(label="Size", menu=size_menu)
    menu.add_checkbutton(label=STARTUP_LABEL, variable=app.startup_var, command=app.on_startup_toggle)
    menu.add_separator()
    menu.add_command(label="Exit", command=app.quit)
    return menu


def refresh_menu(app):
    friend = app.friend is not None
    app.pet_menu.entryconfigure("end", label="Send friend home" if friend else "Invite a friend over",
                                command=app.end_playdate if friend else app.invite_friend)
    app.menu.entryconfigure(app.show_index, label="Stop the show" if app.show else "Put on a show!")
    count = len(app.reminders)
    app.menu.entryconfigure(app.reminder_index, label=f"Active reminders ({count})" if count else "Active reminders")
    rm, fm, now = app.reminder_menu, app.focus_menu, time.time()
    rm.delete(0, "end")
    fm.delete(0, "end")
    for r in sorted(app.reminders, key=lambda r: r["due"]):
        text = r["text"] if len(r["text"]) <= 30 else r["text"][:29] + "..."
        rm.add_command(label=f"Cancel: {text}  (in {fmt_duration(r['due'] - now)})",
                       command=lambda rid=r["id"]: app.cancel_reminder(rid))
    if count:
        rm.add_separator()
        rm.add_command(label="Cancel all", command=app.cancel_reminder)
    else:
        rm.add_command(label="No reminders set", state="disabled")
    if app.focus:
        left = fmt_duration(app.focus["until"] - now)
        fm.add_command(label=f"Focusing, {left} left (round {app.focus['round']})" if app.focus["phase"] == "focus"
                       else f"On a break, {left} left", state="disabled")
        fm.add_command(label="Stop timer", command=app.stop_focus)
    else:
        fm.add_command(label=f"Start ({FOCUS_MIN} min focus / {BREAK_MIN} min break)", command=app.start_focus)
