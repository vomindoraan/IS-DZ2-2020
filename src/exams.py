import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Set, Tuple

from marshmallow_dataclass import dataclass as mm_dataclass

from csp import CSP, Constraint


@mm_dataclass(unsafe_hash=True)
class Exam:
    subject: str = field(metadata={'data_key': 'sifra'})
    n_applied: int = field(metadata={'data_key': 'prijavljeni'})
    needs_computers: bool = field(metadata={'data_key': 'racunari'})
    departments: List[str] = field(metadata={'data_key': 'odseci'})

    def __post_init__(self):
        self.departments = tuple(self.departments)


@mm_dataclass(frozen=True)
class Term:
    duration_days: int = field(metadata={'data_key': 'trajanje_u_danima'})
    exams: List[Exam] = field(metadata={'data_key': 'ispiti'})


@mm_dataclass(frozen=True)
class Hall:
    hall_name: str = field(metadata={'data_key': 'naziv'})
    capacity: int = field(metadata={'data_key': 'kapacitet'})
    has_computers: bool = field(metadata={'data_key': 'racunari'})
    n_proctors: int = field(metadata={'data_key': 'dezurni'})
    belongs_to_etf: bool = field(metadata={'data_key': 'etf'})


@dataclass
class ScheduleSlot:
    start: datetime
    halls: Set[Hall]


@dataclass
class SolutionPair:
    exam: Exam
    slot: ScheduleSlot


TERM_START_DATE = date(2020, 1, 1)
VALID_START_TIMES = (time(8,00), time(11,30), time(15,00), time(18,30))


class ExamSchedulingConstraint(Constraint[Exam, ScheduleSlot]):
    def __init__(self, exams: List[Exam]):
        super().__init__(exams)
        self.exams = exams

    def satisfied(self, assignment: Dict[Exam, ScheduleSlot]) -> bool:
        dept_year_constraints: Dict[date, Set[Tuple[str, int]]] = defaultdict(set)

        for exam, slot in assignment.items():
            # Број распоређених студената у сали не може да премаши капацитет те сале.
            if exam.n_applied > sum(h.capacity for h in slot.halls):
                return False

            # Испити почињу у једном од наведена 4 термина.
            start_day, start_time = slot.start.date(), slot.start.time()
            if start_time not in VALID_START_TIMES:
                return False

            # У једној сали у једном тренутку може да се одржава само један испит.
            concurrent_halls = set()
            for exam1, slot1 in assignment.items():
                if slot1.start == slot.start and exam1 != exam:
                    concurrent_halls.update(slot1.halls)
            if slot.halls & concurrent_halls:
                return False

            # Испити који се полажу на рачунарима могу да се распореде само у сале које
            # поседују рачунаре.
            if exam.needs_computers and any(not h.has_computers for h in slot.halls):
                return False

            # За сваки одсек важи да се у једном дану не могу распоредити два или више
            # испита са исте године студија који се на том одсеку нуде.
            for dept in exam.departments:
                year = int(exam.subject[5])
                constraint = (dept, year)
                if constraint in dept_year_constraints[start_day]:
                    return False
                dept_year_constraints[start_day].add(constraint)

        return True


if __name__ == '__main__':
    import csv
    from itertools import chain, combinations
    from pprint import pprint

    term: Term
    halls: List[Hall]

    i = input("Test #: ")
    with open(f'test/rok{i}.json') as f:
        term = Term.Schema().load(json.load(f))
    with open(f'test/sale{i}.json') as f:
        halls = Hall.Schema(many=True).load(data = json.load(f))

    def powerset(iterable):
        s = list(iterable)
        return chain.from_iterable(combinations(s, r) for r in range(1, len(s)+1))

    schedule_slots = []
    halls_powerset = list(powerset(halls))
    for d in range(term.duration_days):
        day = TERM_START_DATE + timedelta(days=d)
        for time in VALID_START_TIMES:
            start = datetime.combine(day, time)
            for halls_subset in halls_powerset:
                slot = ScheduleSlot(start, set(halls_subset))
                schedule_slots.append(slot)

    variables = term.exams
    domains = {v: schedule_slots.copy() for v in variables}

    csp = CSP(variables, domains)
    csp.add_constraint(ExamSchedulingConstraint(variables))

    solutions = csp.backtracking_search()
    pprint(solutions)

    def filter_by_time(solutions, start):
        for exam, slot in solutions.items():
            if slot.start == start:
                yield SolutionPair(exam, slot)

    with open(f'test/out{i}.csv', mode='w', newline='') as f:
        writer = csv.writer(f)

        for d in range(term.duration_days):
            day_str = f'Dan{d+1}'
            hall_names = map(lambda h: h.hall_name, halls)
            writer.writerow([day_str, *hall_names])

            for time in VALID_START_TIMES:
                day = TERM_START_DATE + timedelta(days=d)
                start = datetime.combine(day, time)
                pairs = list(filter_by_time(solutions, start))

                subjects = []
                for hall in halls:
                    try:
                        pair = next(p for p in pairs if hall in p.slot.halls)
                        subjects.append(pair.exam.subject)
                    except StopIteration:
                        subjects.append('X')

                time_str = time.strftime('%H:%M')
                writer.writerow([time_str, *subjects])

            writer.writerow([])
