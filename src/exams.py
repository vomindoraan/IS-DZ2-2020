import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import chain, combinations
from typing import Dict, List, Optional, Set, Tuple

from marshmallow_dataclass import NewType
from marshmallow_dataclass import dataclass as mm_dataclass

from csp import CSP, Constraint

# class Subject(str):
#     # accreditation: int
#     # study_program: str
#     # parent_department: int
#     # year: int
#     # subject_id: str
#     @property
#     def year(self) -> int:
#         return int(self[5])


@mm_dataclass(unsafe_hash=True)
class Exam:
    subject: str = field(metadata={'data_key': 'sifra'})
    n_applied: int = field(metadata={'data_key': 'prijavljeni'})
    needs_computers: bool = field(metadata={'data_key': 'racunari'})
    departments: List[str] = field(metadata={'data_key': 'odseci'})

    def __post_init__(self):
        self.departments = tuple(self.departments)  # FIXME


@mm_dataclass(frozen=True)
class Term:
    duration_days: int = field(metadata={'data_key': 'trajanje_u_danima'})
    exams: List[Exam] = field(metadata={'data_key': 'ispiti'})


@mm_dataclass(frozen=True)
class Hall:
    hall: str = field(metadata={'data_key': 'naziv'})
    capacity: int = field(metadata={'data_key': 'kapacitet'})
    has_computers: bool = field(metadata={'data_key': 'racunari'})
    n_proctors: int = field(metadata={'data_key': 'dezurni'})
    belongs_to_etf: bool = field(metadata={'data_key': 'etf'})


@dataclass
class ScheduleSlot:
    start: datetime
    halls: Set[Hall]


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
                constraint = (dept, exam.subject[5])  # FIXME
                if constraint in dept_year_constraints[start_day]:
                    return False
                dept_year_constraints[start_day].add(constraint)

        return True


def powerset(iterable):
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s)+1))


if __name__ == '__main__':
    from pprint import pprint

    term:  Term
    halls: List[Hall]

    i = input("Test #: ")
    with open(f'test/rok{i}.json') as f:
        data = json.load(f)
        term = Term.Schema().load(data)
        # print(term)

    with open(f'test/sale{i}.json') as f:
        data = json.load(f)
        halls = Hall.Schema(many=True).load(data)
        # print(halls)

    schedule_slots = []
    halls_powerset = list(powerset(halls))
    for d in range(term.duration_days):
        day = TERM_START_DATE + timedelta(days=d)
        for time in VALID_START_TIMES:
            start = datetime.combine(day, time)
            for halls in halls_powerset:
                slot = ScheduleSlot(start, set(halls))
                schedule_slots.append(slot)

    variables = term.exams
    domains = {v: schedule_slots.copy() for v in variables}

    csp = CSP(variables, domains)
    csp.add_constraint(ExamSchedulingConstraint(variables))

    solution = csp.backtracking_search()
    # pprint(solution)

    def find_items(solution, start):
        items = []
        for exam, slot in solution.items():
            if slot.start == start:
                items.append((exam, slot))
        return items

    with open(f'test/out{i}.csv', mode='w') as f:
        writer = csv.writer(f)

        for d in range(term.duration_days):
            hls = map(lambda h: h.hall, halls)
            writer.writerow([f'Dan{d}', *hls])

            for st in VALID_START_TIMES:
                start = datetime.combine(
                    date=TERM_START_DATE + timedelta(days=d),
                    time=st
                )
                items = find_items(solution, start)
                out = []
                for hall in halls:
                    try:
                        itm = next(i for i in items if hall in i[1].halls)
                        out.append(itm[0].subject)
                    except StopIteration:
                        out.append("X")

                writer.writerow([str(st)[:5], *out])
            writer.writerow([])
