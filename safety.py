
MODE = "observe"  # observe | suggest | autonomous

def can_execute():
    return MODE == "autonomous"
