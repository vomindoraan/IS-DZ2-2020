import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Set, Tuple

import itertools
from marshmallow_dataclass import NewType
from marshmallow_dataclass import dataclass as mm_dataclass

from csp import CSP, Constraint

# @dataclass
# class Subject(str):
#     # accreditation: int
#     # study_program: str
#     # parent_department: int
#     # year: int
#     # subject_id: str
#     @property
#     def year(self) -> int:
#         return int(self[5])
Subject = NewType('Subject', str)


@mm_dataclass(frozen=True)
class Exam:
    subject: Subject = field(metadata={'data_key': 'sifra'})
    n_applied: int = field(metadata={'data_key': 'prijavljeni'})
    needs_computers: bool = field(metadata={'data_key': 'racunari'})
    departments: Tuple[str] = field(metadata={'data_key': 'odseci'})


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
                constraint = (dept, exam.subject.year)
                if constraint in dept_year_constraints[start_day]:
                    return False
                dept_year_constraints[start_day].add(constraint)

        return True


if __name__ == '__main__':
    term:      Term
    halls:     List[Hall]
    timeslots: List[datetime]
    variables: List[Exam]
    domains:   Dict[Exam, List[ScheduleSlot]]
    csp:       CSP[Exam, ScheduleSlot]
    solution:  Optional[Dict[Exam, ScheduleSlot]]

    i = input("Test #: ")
    with open(f'test/rok{i}.json') as f:
        data = json.load(f)
        term = Term.Schema().load(data)
        print(term)

    with open(f'test/sale{i}.json') as f:
        data = json.load(f)
        halls = Hall.Schema(many=True).load(data)
        print(halls)

    timeslots = []
    for d in range(term.duration_days):
        day = TERM_START_DATE + timedelta(days=d)
        for time in VALID_START_TIMES:
            timeslots.append(datetime.combine(day, time))

    schedule_slots = itertools.permutations(halls)
    print(schedule_slots)

    variables = term.exams
    domains = {v: schedule_slots for v in variables}

    csp = CSP(variables, domains)
    csp.add_constraint(ExamSchedulingConstraint(variables))
