from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import (
    Class,
    EducatorProfile,
    Enrollment,
    Material,
    MaterialSection,
    QuizAttempt,
    QuizQuestion,
    ScorePrediction,
    SectionFocusScore,
    StudentProfileEntry,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    User,
    UserLearningProfile,
)
from app.schemas import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserOut
from app.security import create_token, decode_token, hash_password, verify_password
from app.services.focus import compute_focus_score

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(str(user.id), "access"),
        refresh_token=create_token(str(user.id), "refresh"),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> TokenPair:
    existing = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=payload.email.lower(), hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    await db.flush()
    if payload.role == "educator":
        db.add(EducatorProfile(user_id=user.id, bio=payload.bio, institution=payload.institution))
    await db.commit()
    await db.refresh(user)
    return _token_pair(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_pair(user)


SEED_PASSWORD = "edutrack-seed-password"
SEED_USERS: dict[str, dict[str, str]] = {
    "student": {"email": "jordan.lee@edutrack.app"},
    "educator": {"email": "taylor.chen@edutrack.app"},
    "researcher": {"email": "morgan.patel@edutrack.app"},
}
SEED_CLASS_TITLE = "Algebra I · Block 3"
SEED_CLASS_CODE = "ALG2026A"
SEED_LESSON_A_TITLE = "Introduction to the Pythagorean Theorem"
SEED_LESSON_B_TITLE = "Solving One-Step Linear Equations"

# Backwards-compatibility aliases — older tests import these names.
DEMO_USERS = SEED_USERS
DEMO_CLASS_CODE = SEED_CLASS_CODE
DEMO_CLASS_TITLE = SEED_CLASS_TITLE
DEMO_LESSON_TITLE = SEED_LESSON_A_TITLE


class DemoLoginRequest(BaseModel):
    role: Literal["student", "educator", "researcher"]


async def _ensure_seed_user(db: AsyncSession, role: str) -> User:
    info = SEED_USERS[role]
    email = info["email"]
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, hashed_password=hash_password(SEED_PASSWORD), role=role)
        db.add(user)
        await db.flush()
        if role == "educator":
            db.add(
                EducatorProfile(
                    user_id=user.id,
                    bio="Math teacher, 8 years",
                    institution="Lincoln Public School",
                )
            )
        await db.flush()
    return user


_LESSON_A_SECTIONS = [
    (
        "Why the Pythagorean theorem matters",
        """## The big idea

Imagine you are walking across a rectangular park. Instead of walking along two sides of the rectangle, you cut
diagonally through the middle. You have just used the Pythagorean theorem without ever writing down a formula —
your shortcut worked because the diagonal, the long side, and the short side of the park form a **right triangle**,
and those three sides follow a strict mathematical relationship.

The Pythagorean theorem is one of the oldest and most-used results in mathematics. It shows up when you set up a
TV, lay out a garden, design a ramp, plan a route on a map, or write a video game that needs to know how far two
things are apart. It is also the gateway to **distance**, to **vectors**, to **trigonometry**, and eventually to
calculus. Learning it well now pays off for years.

This lesson has three goals. First, we will make sure you can *recognize* a right triangle and *label* its parts
without hesitation. Second, we will build up the formula a² + b² = c² until it feels less like a rule you memorize
and more like a picture you can see. Third, we will practice enough that applying it becomes automatic — that is
what will matter when a harder problem tries to disguise a Pythagorean setup inside it.

Before you reach for the formula, keep this habit in mind: **label first, compute second**. Most mistakes at this
level are not arithmetic mistakes; they are labeling mistakes. If you always stop, find the right angle, and
identify the hypotenuse, you will avoid most of the pitfalls people run into.""",
        0,
    ),
    (
        "Right triangles and their parts",
        """## Spotting the right angle

A **right triangle** has exactly one 90° angle — the square corner. That angle is usually marked with a small
square inside the corner rather than the usual arc used for other angles. If you see that tiny square, you are
looking at a right triangle.

The two sides that come together to form the right angle are called the **legs**. They are traditionally labeled
*a* and *b*. It does not matter which leg you call *a* and which one you call *b*; the theorem is symmetric in the
two legs.

The side opposite the right angle — the one that doesn't touch the square corner — is called the **hypotenuse**,
labeled *c*. The hypotenuse has two special properties worth remembering:

- It is always the **longest** side of the triangle.
- It is always **opposite** the right angle, never next to it.

## A small checklist

Before you use the theorem on a triangle, run this four-step check:

1. Is there a right angle? If not, stop — the theorem does not apply.
2. Which side is opposite the right angle? That is your *c*.
3. Pick either remaining side and call it *a*.
4. The last remaining side is *b*.

Getting this right is the single most reliable predictor of success on Pythagorean problems. Students who slow down
for fifteen seconds and label the triangle with a pencil miss far fewer questions than students who jump straight
into the algebra.""",
        1,
    ),
    (
        "Watch: the theorem in action",
        "YT::AA6RfgP-AHU::Khan Academy walks through the Pythagorean theorem with a visual proof and two examples.",
        2,
    ),
    (
        "The core relationship: a² + b² = c²",
        """## The statement, in words and symbols

The **Pythagorean theorem** states that in any right triangle, the square of the hypotenuse equals the sum of the
squares of the two legs:

> a² + b² = c²

In plain English: if you build a square on each of the three sides of a right triangle, the areas of the two
smaller squares add up to exactly match the area of the big square built on the hypotenuse. That visual — three
squares, two stacking to match the third — is the picture to keep in your head.

## What the symbols actually mean

Remember that *a*, *b*, and *c* are **lengths**, but a², b², and c² are **areas**. The algebra is a statement
about areas more than it is a statement about lengths. That is why you can't just add *a* and *b* and expect to
get *c*; if a = 3 and b = 4, then a + b = 7, but the hypotenuse is actually 5, because 3² + 4² = 9 + 16 = 25 and
the square root of 25 is 5.

## When it applies

The theorem only applies when the triangle is a right triangle. If the largest angle is less than 90° the triangle
is *acute* and a² + b² > c². If the largest angle is more than 90° the triangle is *obtuse* and a² + b² < c². In
fact, you can use those inequalities as a classification tool: compute a² + b² and compare it to c². This
relationship is the seed of the **Law of Cosines**, which you will meet in trigonometry.""",
        3,
    ),
    (
        "A worked example, step by step",
        """## Example 1 — Find the hypotenuse

Suppose a right triangle has legs of length **3** and **4**. Find the hypotenuse.

1. Label: a = 3, b = 4, c = ?
2. Apply the theorem: a² + b² = c² becomes 3² + 4² = c².
3. Compute the squares: 9 + 16 = c², which gives 25 = c².
4. Take the positive square root: c = √25 = **5**.
5. Check: is c longer than either leg? Yes, 5 > 4. The answer is consistent.

## Example 2 — Find a missing leg

Suppose the hypotenuse is **13** and one leg is **5**. Find the other leg.

1. Label: a = 5, b = ?, c = 13.
2. Apply the theorem: 5² + b² = 13².
3. Compute the squares you know: 25 + b² = 169.
4. Isolate b²: b² = 169 − 25 = 144.
5. Take the positive square root: b = √144 = **12**.
6. Check: is c the longest side? Yes, 13 > 12 and 13 > 5. The answer is consistent.

## Common Pythagorean triples worth memorizing

A **Pythagorean triple** is a set of three whole numbers that satisfy a² + b² = c². Spotting one inside a problem
lets you skip the arithmetic.

- **(3, 4, 5)** and its multiples (6, 8, 10), (9, 12, 15), (12, 16, 20)…
- **(5, 12, 13)** and its multiples (10, 24, 26), (15, 36, 39)…
- **(8, 15, 17)**
- **(7, 24, 25)**
- **(20, 21, 29)**

When you see two of the three numbers of a well-known triple, the third one is usually the answer.""",
        4,
    ),
    (
        "Using the theorem backward",
        """## When the problem hides the triangle

Most real-world Pythagorean problems don't hand you a picture of a triangle with nicely labeled sides. Instead,
they describe a situation, and *you* have to spot the right triangle inside it.

Classic patterns to recognize:

- A **ladder leaning against a wall** forms a right triangle with the wall (one leg), the ground (the other leg),
  and the ladder itself (the hypotenuse).
- The **diagonal of a rectangle** splits it into two right triangles whose legs are the rectangle's sides and
  whose hypotenuse is the diagonal.
- The **shortest path between two points** on a grid (if diagonals are allowed) is the hypotenuse of the right
  triangle whose legs are the horizontal and vertical distances.
- A **TV screen size** is the hypotenuse; the width and height are the legs.

## Example — the ladder problem

A 10-foot ladder leans against a wall. Its base is 6 feet from the wall. How high up the wall does it reach?

1. Draw the picture: ladder (c = 10), base-to-wall (a = 6), wall height (b = ?).
2. Apply: a² + b² = c² becomes 6² + b² = 10².
3. Compute: 36 + b² = 100, so b² = 64.
4. Take the root: b = 8. The ladder reaches **8 feet** up the wall.

## Finding the distance between two points

Given two points (x₁, y₁) and (x₂, y₂) on a plane, the distance between them is the hypotenuse of a right
triangle whose legs are the horizontal and vertical differences:

> distance = √((x₂ − x₁)² + (y₂ − y₁)²)

This is one of the most useful formulas in all of mathematics and it is literally just the Pythagorean theorem
with the square root moved to the left side.""",
        5,
    ),
    (
        "Common mistakes and how to avoid them",
        """## Mistake 1 — Using it on a non-right triangle

The theorem only works when there is a 90° angle. If the problem doesn't mention a right angle, mark of square
corner, or any words like "perpendicular" or "vertical and horizontal," check before you use the formula.

## Mistake 2 — Confusing which side is the hypotenuse

The hypotenuse is *always* opposite the right angle. Students sometimes pick the longest-looking side even when the
diagram is not to scale. Trust the 90° mark over how the drawing looks.

## Mistake 3 — Forgetting to take the square root at the end

It is easy to compute a² + b² = c² and write down the value of c² as your final answer. Always take the positive
square root as the last step. A quick sanity check — "is my answer longer than either leg?" — catches this one.

## Mistake 4 — Adding instead of squaring

a + b ≠ c. It is tempting to skip the squaring step, but the whole relationship breaks if you do. Write the square
symbols explicitly every time until it is automatic.

## Mistake 5 — Sign errors

When you solve for a leg, you subtract: a² = c² − b². If you accidentally add when you should subtract, your b²
term will be too big and the square root won't be a clean number. If a problem that should have a whole-number
answer doesn't give you one, re-check your sign.""",
        6,
    ),
    (
        "Checkpoint before the quiz",
        """## Quick recap

- A right triangle has one 90° angle. The two sides forming that angle are the legs (a and b); the side opposite
  is the hypotenuse (c). The hypotenuse is always the longest side.
- The Pythagorean theorem says a² + b² = c². It only applies to right triangles.
- To find the hypotenuse: a² + b² = c², then square root.
- To find a leg: a² = c² − b², then square root.
- Memorize the common triples: (3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25).
- Before you compute, label your triangle. Before you finish, sanity-check: c must be longer than a or b.

## What to do next

Read back through your worked examples one more time. Cover the answer and try to redo the arithmetic in your
head. If you can do the first example (3, 4, 5) in under ten seconds, you are ready for the quiz.

If a step still feels mechanical instead of obvious, rewatch the embedded video above and pay attention to where
it draws the three squares — that visual is what makes the algebra stick.""",
        7,
    ),
]

_LESSON_A_QUESTIONS = [
    (
        "In the equation a² + b² = c², what is c?",
        ["The shortest side", "A leg of the triangle", "The hypotenuse", "The area of the triangle"],
        "The hypotenuse",
    ),
    (
        "A right triangle has legs of length 6 and 8. What is the hypotenuse?",
        ["10", "12", "14", "100"],
        "10",
    ),
    (
        "Which triangle CANNOT use the Pythagorean theorem directly?",
        [
            "A triangle with sides 3, 4, 5",
            "An equilateral triangle with all sides equal",
            "A triangle with a 90° angle",
            "A 5-12-13 triangle",
        ],
        "An equilateral triangle with all sides equal",
    ),
    (
        "If the hypotenuse is 13 and one leg is 5, what is the other leg?",
        ["8", "12", "14", "18"],
        "12",
    ),
]

_LESSON_B_SECTIONS = [
    (
        "What is an equation, really?",
        """## A statement of equality

An **equation** is a sentence in the language of math that says two things are the same. The equals sign (=) is
the verb. Everything to the left of it is one expression; everything to the right is another expression; and the
equation claims they have the same numerical value. That's it.

Some equations are always true: 2 + 2 = 4 is an equation that requires no thought. Others are only true for
specific values of their variables: x + 3 = 7 is only true when x = 4. Our job as algebra students is to take
equations of the second kind and figure out which values make them true.

## Why the balance metaphor works

Picture an old-fashioned two-pan balance scale. On the left pan you have the left side of the equation; on the
right pan you have the right side. Because the equation is *equal*, the scale is perfectly level.

If you add something to the left pan, the scale tips left — and the equation is no longer true. If you add the
same something to both pans, the scale stays level and the equation stays true. This is the single rule that
governs everything else in algebra:

> **Whatever you do to one side of an equation, you must do to the other.**

Every step of every algebra problem, from the simplest one-step equation to the most tangled college-level
system, is a controlled application of this single rule. Memorize it. Trust it. Return to it whenever you are
unsure what to do next.

## What we're aiming for

The goal of solving a linear equation is to **isolate the variable** — to end up with a statement of the form
`x = (something)` where the right side is a number. Once x is alone, you can just read off the answer.""",
        0,
    ),
    (
        "Inverse operations: the toolkit",
        """## Operations and their undos

Every arithmetic operation has an **inverse** — an operation that undoes it. These inverses are the only tools
you need for one-step equations:

| Operation on x | Inverse (apply to both sides) |
| --- | --- |
| Addition: x + 3 | Subtract 3 |
| Subtraction: x − 3 | Add 3 |
| Multiplication: 4x | Divide by 4 |
| Division: x/4 | Multiply by 4 |

## Choosing the inverse

Look at what is being *done* to x, then pick the matching inverse. Two quick rules:

- If the operation adds or subtracts, its inverse also adds or subtracts.
- If the operation multiplies or divides, its inverse also multiplies or divides.

If x + 7 = 12, the thing being done to x is "+7", so the inverse is "−7". We subtract 7 from both sides.

If 4x = 20, the thing being done to x is "×4", so the inverse is "÷4". We divide both sides by 4.

## Why this works, not just that it does

The inverse gets x alone because the operation and its inverse cancel: (+7) and (−7) net to 0, and (×4) and
(÷4) net to 1. So doing the inverse to both sides turns the side with x into just x, which is exactly the
isolate-the-variable goal.

## A common trap

Students sometimes "undo" an operation by doing *the same operation* instead of the inverse. For instance,
given 4x = 20, they multiply both sides by 4. Now they have 16x = 80, which is further from solved, not closer.
Always reach for the *inverse*, not the repeat.""",
        1,
    ),
    (
        "Watch: solving step by step",
        "YT::9Ek61w1LxSc::Khan Academy walks through several one-step equations, talking through the balance idea as they go.",
        2,
    ),
    (
        "A worked example with commentary",
        """## Example 1 — Solve x − 3 = 8

**Step 1: Identify the operation on x.**
The variable x has a 3 subtracted from it.

**Step 2: Choose the inverse.**
The inverse of "subtract 3" is "add 3".

**Step 3: Apply to both sides.**

```
x − 3 = 8
x − 3 + 3 = 8 + 3
x = 11
```

**Step 4: Check by substituting back.**
11 − 3 = 8. ✓ Correct.

## Example 2 — Solve x/5 = 4

**Step 1: Identify the operation.**
The variable x is being divided by 5.

**Step 2: Inverse.**
Multiply by 5.

**Step 3: Apply to both sides.**

```
x/5 = 4
(x/5) · 5 = 4 · 5
x = 20
```

**Step 4: Check.**
20/5 = 4. ✓ Correct.

## Example 3 — Solve 2x = 14

Done mentally: the inverse of ×2 is ÷2, so x = 14/2 = 7. Check: 2·7 = 14. ✓

## Example 4 — Solve x + 11 = 4 (negative answers are fine)

**Inverse:** subtract 11. x = 4 − 11 = **−7**. Check: −7 + 11 = 4. ✓

Negative answers are normal; don't second-guess the arithmetic just because the number is less than zero.""",
        3,
    ),
    (
        "Why substituting back is worth the seconds",
        """## The check step

Every solved equation gives you a free sanity check: take your answer, plug it back into the original equation,
and see if the two sides match. If they do, you are done. If they don't, you made an arithmetic mistake or an
inverse-operation mistake — and catching it now is much less painful than catching it on the quiz.

The check takes about ten seconds. There is no reason to skip it.

## Two ways a check can fail

1. **The sides don't match.** Somewhere, you did the wrong operation or made an arithmetic slip. Try again from
   the original equation, not from a later step (since the mistake could be in one of those later steps).
2. **You got an inequality instead of an equation.** This can happen if you treated a subtraction as an addition.
   Re-read the original problem carefully.

## A habit to build

When you are first learning, always write the check out explicitly:

```
Solution: x = 11.
Check: 11 − 3 = 8 ✓
```

Once you have done this a few dozen times, you will be fast enough at it that you can do it in your head on easy
problems, and you will reserve the written check for harder problems where you actually need it.""",
        4,
    ),
    (
        "Negative numbers, fractions, and other nuisances",
        """## Don't fear the negative

Students sometimes panic when an equation produces a negative intermediate value. Treat negatives as regular
numbers — apply the inverse operation the same way. For instance:

**Solve x + 9 = 3.**
Subtract 9 from both sides: x = 3 − 9 = **−6**.
Check: −6 + 9 = 3. ✓

## Fractional coefficients

When x is multiplied by a fraction, dividing by the fraction is the same as multiplying by its reciprocal. That
is usually the cleaner move.

**Solve (2/3)x = 8.**
The inverse of "multiply by 2/3" is "multiply by 3/2".
x = 8 · (3/2) = 24/2 = **12**.
Check: (2/3) · 12 = 24/3 = 8. ✓

## Keeping signs straight

If you move a term across the equals sign (by subtracting it from both sides), its sign flips. That is really just
the "subtract from both sides" rule in shorthand — but it is where many mistakes are made. Write the step out if
you need to. Speed comes from accuracy, not from skipping steps.""",
        5,
    ),
    (
        "Common mistakes and how to avoid them",
        """## Mistake 1 — Applying the operation to only one side

The single most common mistake in all of algebra. Always operate on both sides. If you find yourself writing just
one side of a step, stop and rewrite it.

## Mistake 2 — Same operation instead of the inverse

Multiplying both sides by 4 when the equation already has 4x makes the problem worse. Reach for the **inverse**,
not the repeat.

## Mistake 3 — Forgetting to distribute

Later problems look like 3(x + 2) = 15. If you try to "subtract 3" from both sides, the equation breaks. The
right move is either (a) divide both sides by 3 first, or (b) distribute the 3 through the parentheses. Either
works; just don't treat the 3 as if it is simply added.

## Mistake 4 — Sign errors

Read the sign of each term before you move it. A minus sign that got ignored in step 2 will poison every step
afterward. Slow down on the setup; speed up on the arithmetic.

## Mistake 5 — Skipping the check

If you ever solve an equation and the "answer" surprises you — too big, too small, or a weird fraction — plug it
back in before you move on. The check takes ten seconds and saves ten minutes.""",
        6,
    ),
    (
        "Checkpoint before the quiz",
        """## The one idea

To solve a one-step linear equation: identify the operation on x, apply the inverse operation to both sides, and
check your answer.

## A short self-test

Without looking back, try to answer these in your head:

- If x + 6 = 10, what is x?
- If 3x = 21, what is x?
- If x/2 = 9, what is x?
- If x − 4 = −1, what is x?

Answers: 4, 7, 18, 3. If you got three or four right on the first try, you are ready for the quiz.

## If you want a stretch

Next lesson, we will look at two-step equations like 2x + 3 = 11, which still follow the same balance rule but
need the inverses applied in order. Everything you learned here is a building block for that. Don't rush — get
the one-step pattern automatic before you layer complexity on top.""",
        7,
    ),
]

_LESSON_B_QUESTIONS = [
    (
        "Solve for x: x + 9 = 15",
        ["4", "6", "24", "-6"],
        "6",
    ),
    (
        "Solve for x: 3x = 21",
        ["3", "6", "7", "24"],
        "7",
    ),
    (
        "Solve for x: x / 4 = 5",
        ["1", "9", "20", "45"],
        "20",
    ),
    (
        "Which operation undoes subtraction?",
        ["Subtraction", "Addition", "Multiplication", "Division"],
        "Addition",
    ),
]


async def _ensure_seed_lesson(
    db: AsyncSession,
    *,
    class_id: int,
    title: str,
    order_index: int,
    sections: list[tuple[str, str, int]],
    questions: list[tuple[str, list[str], str]],
) -> None:
    existing = await db.scalar(
        select(Material).where(Material.class_id == class_id, Material.title == title)
    )
    if existing is not None:
        return
    material = Material(
        class_id=class_id,
        title=title,
        type="lesson",
        order_index=order_index,
        published_at=datetime.now(UTC),
    )
    db.add(material)
    await db.flush()
    for section_title, content, order in sections:
        db.add(
            MaterialSection(
                material_id=material.id,
                title=section_title,
                content=content,
                order_index=order,
                word_count=len(content.split()),
            )
        )
    for question, options, correct in questions:
        db.add(
            QuizQuestion(
                material_id=material.id,
                question=question,
                options=options,
                correct_answer=correct,
                points=1.0,
            )
        )


async def _ensure_demo_world(db: AsyncSession) -> None:
    student = await _ensure_seed_user(db, "student")
    educator = await _ensure_seed_user(db, "educator")
    await _ensure_seed_user(db, "researcher")

    cls = await db.scalar(select(Class).where(Class.enrollment_code == SEED_CLASS_CODE))
    if cls is None:
        cls = Class(
            educator_id=educator.id,
            title=SEED_CLASS_TITLE,
            description=(
                "A first-semester algebra block covering right triangles, linear equations, and the "
                "habits of mind that make the rest of high-school math feel reachable."
            ),
            enrollment_code=SEED_CLASS_CODE,
        )
        db.add(cls)
        await db.flush()

    enrolled = await db.scalar(
        select(Enrollment.id).where(Enrollment.class_id == cls.id, Enrollment.student_id == student.id)
    )
    if not enrolled:
        db.add(Enrollment(class_id=cls.id, student_id=student.id))
        await db.flush()

    await _ensure_seed_lesson(
        db,
        class_id=cls.id,
        title=SEED_LESSON_A_TITLE,
        order_index=0,
        sections=_LESSON_A_SECTIONS,
        questions=_LESSON_A_QUESTIONS,
    )
    await _ensure_seed_lesson(
        db,
        class_id=cls.id,
        title=SEED_LESSON_B_TITLE,
        order_index=1,
        sections=_LESSON_B_SECTIONS,
        questions=_LESSON_B_QUESTIONS,
    )
    await db.commit()
    await _ensure_seed_student_activity(db, student_id=student.id, class_id=cls.id)


# ------------------------------------------------------------------
# Simulated student history for the seed student so the UI renders
# with real content instead of empty-state placeholders.
# ------------------------------------------------------------------


def _seed_features(*, focused: bool, word_count: int) -> dict:
    """Plausible feature dict for a single seeded session."""
    if focused:
        return {
            "total_time_s": 240,
            "time_per_section": {},
            "hover_count": 5,
            "avg_hover_duration_ms": 900,
            "hover_per_section": {},
            "scroll_depth_pct": 95,
            "back_scroll_count": 2,
            "scroll_velocity_avg": 0.4,
            "mouse_velocity_avg": 0.3,
            "mouse_velocity_variance": 4.5,
            "idle_total_s": 6,
            "idle_count": 1,
            "text_selection_count": 3,
            "re_read_sections": ["1"],
            "reading_speed_wpm": 190,
            "section_completion_rate": 1.0,
        }
    return {
        "total_time_s": 150,
        "time_per_section": {},
        "hover_count": 1,
        "avg_hover_duration_ms": 300,
        "hover_per_section": {},
        "scroll_depth_pct": 60,
        "back_scroll_count": 8,
        "scroll_velocity_avg": 1.4,
        "mouse_velocity_avg": 2.1,
        "mouse_velocity_variance": 180,
        "idle_total_s": 55,
        "idle_count": 3,
        "text_selection_count": 0,
        "re_read_sections": [],
        "reading_speed_wpm": 110,
        "section_completion_rate": 0.55,
    }


_NARRATIVE_NOTES = [
    "Reads worked examples slowly and carefully; retention is strong when geometry is drawn out.",
    "Loses focus in proof-heavy passages after about two minutes; benefits from a concrete warm-up.",
    "High re-read behavior on definitions — likes to anchor vocabulary before moving on.",
]


async def _ensure_seed_student_activity(db: AsyncSession, *, student_id: int, class_id: int) -> None:
    existing = await db.scalar(
        select(TrackingSession.id).where(TrackingSession.student_id == student_id).limit(1)
    )
    if existing is not None:
        return

    materials = (
        await db.scalars(
            select(Material)
            .where(Material.class_id == class_id)
            .order_by(Material.order_index.asc())
            .options(selectinload(Material.sections), selectinload(Material.questions))
        )
    ).all()
    if not materials:
        return

    now = datetime.now(UTC)
    # Pattern: two sessions per lesson (a focused then a shakier one), ordered so the
    # most recent sits at the end. This produces a realistic learning arc.
    pattern = [
        ("A", True, 5),  # lesson A, focused, 5 days ago
        ("B", False, 4),
        ("A", False, 3),
        ("B", True, 2),
        ("A", True, 1),
    ]
    lesson_by_tag = {"A": materials[0], "B": materials[1] if len(materials) > 1 else materials[0]}

    # Quiz scores for each session, hand-tuned so mastery drifts up over time.
    score_pattern = [0.75, 0.5, 0.6, 0.8, 0.9]

    for index, (tag, focused, days_ago) in enumerate(pattern):
        material = lesson_by_tag[tag]
        sections = list(material.sections)
        questions = list(material.questions)
        word_count = sum(s.word_count for s in sections) or 400

        started = now - timedelta(days=days_ago, minutes=5)
        ended = started + timedelta(minutes=5 if focused else 3)
        features = _seed_features(focused=focused, word_count=word_count)
        focus = compute_focus_score(features)

        session = TrackingSession(
            student_id=student_id,
            material_id=material.id,
            started_at=started,
            ended_at=ended,
            features=features,
            focus_score=focus["focus_score"],
            focus_breakdown=focus["breakdown"],
            focus_label=focus["label"],
        )
        db.add(session)
        await db.flush()

        # Per-section focus rows.
        for section in sections:
            per_section_score = focus["focus_score"] * (0.95 if focused else 0.8)
            per_section_label = "focused" if focused else "skimmed"
            db.add(
                SectionFocusScore(
                    session_id=session.id,
                    section_id=section.id,
                    focus_score=round(min(1.0, per_section_score), 4),
                    breakdown={
                        "pace": focus["breakdown"]["pace"],
                        "attention": focus["breakdown"]["attention"],
                        "engagement": focus["breakdown"]["engagement"],
                        "time_s": round(features["total_time_s"] / max(len(sections), 1), 3),
                        "idle_ratio": round(features["idle_total_s"] / max(features["total_time_s"], 1.0), 4),
                        "re_read_count": 1 if focused and section.order_index == 0 else 0,
                    },
                    label=per_section_label,
                )
            )

        # Score prediction row (heuristic-tier so analytics has something to show).
        db.add(
            ScorePrediction(
                session_id=session.id,
                predicted_score=round(0.5 + 0.2 * (focus["focus_score"] - 0.5), 4),
                confidence=0.45,
                model_version="heuristic-v1",
                actual_score=score_pattern[index],
            )
        )

        # Quiz attempt so the profile + mastery has quiz-grounded signal.
        if questions:
            max_score = float(len(questions))
            raw_score = round(score_pattern[index] * max_score, 4)
            answers = {str(q.id): q.correct_answer for q in questions}
            attempt = QuizAttempt(
                student_id=student_id,
                material_id=material.id,
                session_id=session.id,
                answers=answers,
                score=raw_score,
                max_score=max_score,
                started_at=started,
                submitted_at=ended + timedelta(minutes=2),
            )
            db.add(attempt)
            await db.flush()

            # Append-only profile entry so the researcher view / student narrative
            # shows recent observations.
            normalized = raw_score / max_score if max_score else 0.0
            profile_json = {
                "topic": material.title,
                "observed_score": round(normalized, 4),
                "predicted_score": round(0.5 + 0.2 * (focus["focus_score"] - 0.5), 4),
                "strengths_observed": ["reads the worked example carefully"] if focused else ["attempted the workflow"],
                "struggles_observed": ["needs more scaffolding before independent recall"] if not focused else ["could push harder on edge cases"],
                "engagement_notes": f"focus {focus['label']}, completion {features['section_completion_rate']:.2f}",
                "behavioral_summary": "slow careful reader, benefits from visual aids" if focused else "fast reader, easily distracted by dense proofs",
                "recommendation": "lead with a worked example, then the formal rule" if focused else "use shorter passages and a checkpoint question between sections",
            }
            profile_text = (
                f"Topic: {profile_json['topic']}. Observed score: {profile_json['observed_score']}. "
                f"Strengths: {', '.join(profile_json['strengths_observed'])}. "
                f"Struggles: {', '.join(profile_json['struggles_observed'])}. "
                f"Engagement: {profile_json['engagement_notes']}. "
                f"Behavior: {profile_json['behavioral_summary']}. "
                f"Recommendation: {profile_json['recommendation']}."
            )
            db.add(
                StudentProfileEntry(
                    user_id=student_id,
                    profile_text=profile_text,
                    profile_json=profile_json,
                    embedding=None,
                    trigger_material_id=material.id,
                    quiz_attempt_id=attempt.id,
                    quiz_score=normalized,
                    created_at=ended + timedelta(minutes=2),
                )
            )

    # User learning profile summary — reflects the most-recent session (focused).
    profile = UserLearningProfile(
        user_id=student_id,
        style_vector={
            "pace": 0.55,
            "depth": 0.72,
            "attention_stability": 0.58,
            "engagement_mode": 0.7,
            "revisit_tendency": 0.66,
            "visual_orientation": 0.74,
            "motor_style": 0.55,
        },
        rolling_focus_score=0.74,
        rolling_reading_speed_wpm=172.0,
        rolling_completion_rate=0.86,
        preferred_session_length_s=240.0,
        peak_focus_time_of_day={"histogram": {str((now - timedelta(days=i)).hour): 1 for i in range(5)}, "peak_hour": str(now.hour)},
        engagement_fingerprint={
            "hover_heavy": 0.7,
            "selector": 0.6,
            "re_reader": 0.75,
            "back_scroller": 0.35,
            "skimmer": 0.15,
            "session_samples": len(pattern),
        },
        behavioral_signals={
            "narrative_notes": [
                {"note": note, "ts": (now - timedelta(days=i + 1)).isoformat()}
                for i, note in enumerate(_NARRATIVE_NOTES)
            ],
            "content_preferences": {
                "prefers_examples_before_theory": 0.8,
                "benefits_from_section_summaries": 0.65,
                "tolerates_long_prose": 0.4,
            },
            "recent_hints": [
                "lead with a concrete worked example",
                "break proofs into 2-3 sentence chunks",
                "keep sections under 180 words",
            ],
        },
        session_count=len(pattern),
        lesson_count=len(pattern),
        quiz_count=len(pattern),
        last_focus_label="focused",
    )
    db.add(profile)

    # Topic mastery graph — a handful of topics with varied mastery so the tree view
    # renders red, amber, and green nodes and a few co-occurrence edges.
    topic_signals = [
        ("pythagorean theorem", 0.82, 0.85, 3, 2, 0.05, 0.7),
        ("right triangles", 0.78, 0.8, 3, 2, 0.1, 0.62),
        ("hypotenuse", 0.7, 0.75, 2, 1, 0.15, 0.55),
        ("linear equations", 0.58, 0.72, 2, 2, 0.35, 0.3),
        ("inverse operations", 0.48, 0.6, 2, 1, 0.6, 0.2),
        ("solving equations", 0.5, 0.65, 2, 1, 0.55, 0.25),
        ("algebra balance", 0.4, 0.5, 1, 0, 0.65, 0.1),
    ]
    for topic, mastery, exposure, encounters, quiz_n, struggle, strength in topic_signals:
        db.add(
            TopicMasteryNode(
                user_id=student_id,
                topic=topic,
                mastery_score=mastery,
                exposure_score=exposure,
                encounter_count=encounters,
                quiz_sample_count=quiz_n,
                struggle_signal=struggle,
                strength_signal=strength,
                last_seen_at=now - timedelta(days=1),
                embedding=None,
            )
        )

    co_occur_pairs = [
        ("pythagorean theorem", "right triangles"),
        ("right triangles", "hypotenuse"),
        ("pythagorean theorem", "hypotenuse"),
        ("linear equations", "inverse operations"),
        ("linear equations", "solving equations"),
        ("solving equations", "algebra balance"),
    ]
    for a, b in co_occur_pairs:
        for src, dst in ((a, b), (b, a)):
            db.add(
                TopicMasteryEdge(
                    user_id=student_id,
                    from_topic=src,
                    to_topic=dst,
                    relation="co_occurred",
                    weight=2.0,
                    last_seen_at=now - timedelta(days=1),
                )
            )
    await db.commit()


# Back-compat alias for callers/tests that imported the old name.
_ensure_demo_user = _ensure_seed_user


@router.post("/demo", response_model=TokenPair)
async def demo_login(payload: DemoLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    """Seed the shared test world on demand and return a token for the requested role.

    Three seeded users (student/educator/researcher) share one class with two published
    lessons + quizzes. The student is pre-enrolled, so every role lands in a usable
    dashboard without registration.
    """
    await _ensure_demo_world(db)
    user = await db.scalar(select(User).where(User.email == SEED_USERS[payload.role]["email"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Seed failed")
    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        decoded = decode_token(payload.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    user = await db.scalar(select(User).where(User.id == int(decoded["sub"])))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return _token_pair(user)

