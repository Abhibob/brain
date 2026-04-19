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
SEED_LESSON_C_TITLE = "Slope and Linear Graphs"
SEED_LESSON_D_TITLE = "Systems of Linear Equations"

# Additional "filler" classes the seed student is enrolled in so the dashboard
# doesn't look empty. These have no materials on purpose — they're just stub rows.
SEED_FILLER_CLASSES: list[dict[str, str]] = [
    {
        "title": "Biology 101",
        "description": "Cells, genetics, and the rules that govern living systems. Fall lab block.",
        "code": "BIO2026A",
    },
    {
        "title": "World History · Period 2",
        "description": "From the agricultural revolution to the modern era — emphasis on turning points.",
        "code": "HIST2026B",
    },
    {
        "title": "English Literature · Block 5",
        "description": "Close reading of novels, short stories, and poetry. Weekly writing workshop.",
        "code": "ENG2026E",
    },
    {
        "title": "Introduction to Chemistry",
        "description": "Atoms, bonds, stoichiometry. Includes a weekly lab notebook assignment.",
        "code": "CHEM2026A",
    },
    {
        "title": "Computer Science Foundations",
        "description": "Variables, loops, functions, and problem decomposition — taught in Python.",
        "code": "CS2026A",
    },
    {
        "title": "Spanish II",
        "description": "Builds on year-one basics: past tenses, conversational fluency, short essays.",
        "code": "ESP2026B",
    },
]

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


_LESSON_C_SECTIONS = [
    (
        "Why slope matters",
        """## The idea

Every line on a graph has two things that describe it completely: where it crosses the vertical axis, and how
steeply it goes up or down as you move to the right. The second of these — steepness — is what we call the
**slope**. It shows up everywhere: the price of gas per gallon, the speed of a car, the growth of a savings
account. Whenever a quantity changes at a steady rate, a linear graph is the right picture, and the slope is the
one number that captures that rate.

This lesson has three goals. First, be able to *read* slope from a graph without a ruler. Second, *compute*
slope from two points with no confusion about which subtraction goes on top. Third, *interpret* a slope in plain
words, because a number without units is not yet a useful answer.

Before you jump to formulas, internalize the habit: before you compute, look. Linear graphs tell you their
slope at a glance — up-and-to-the-right is positive, down-and-to-the-right is negative, flat is zero, and
straight-up is undefined. If your computed slope disagrees with what the graph shows, the formula has the bug,
not the picture.""",
        0,
    ),
    (
        "Slope as rise over run",
        """## The ratio

Slope is the ratio of vertical change to horizontal change — how much you go **up** for every step you take to
the **right**. In symbols:

> slope = rise / run = Δy / Δx

The Greek capital delta (Δ) just means "change in." If you move from one point to another along a line, Δy is
the change in the y-value, and Δx is the change in the x-value. The order matters: it is always change-in-y on
top and change-in-x on the bottom, never the other way around.

## A concrete count

Pick two grid points on a line that land on lattice intersections. Starting at the left one:

1. Count the squares you go up or down to reach the right point's height. That count (with sign) is the rise.
2. Count the squares you move right to reach the right point's column. That count is the run.
3. Divide rise by run. That's your slope.

If the line goes down from left to right, the rise is negative. If the line is perfectly flat, the rise is zero
and so is the slope. If the line is perfectly vertical, the run is zero — and division by zero is why the slope
is *undefined* for vertical lines, not "infinite" as a casual word might suggest.""",
        1,
    ),
    (
        "Watch: slope, intercept, and the line",
        "YT::2UrcUfBizyw::Khan Academy walks through slope and the slope-intercept form with three graph examples.",
        2,
    ),
    (
        "The formula from two points",
        """## Two-point slope

Most textbook problems give you two points on a line, written as (x₁, y₁) and (x₂, y₂). The slope is:

> m = (y₂ − y₁) / (x₂ − x₁)

The letter *m* for slope is traditional and you'll see it everywhere. The numerator is the rise; the denominator
is the run. It doesn't matter which point you call "point 1" and which you call "point 2," as long as you are
consistent — that is, if you subtract the point-A values from the point-B values in the numerator, you have to
do the same order in the denominator.

## Example

Points (2, 3) and (5, 9). Slope:

> m = (9 − 3) / (5 − 2) = 6 / 3 = **2**

Check with the picture: from (2, 3) to (5, 9), you go up 6 and right 3 — 6/3 = 2. ✓

Another: (−1, 4) and (3, −4).

> m = (−4 − 4) / (3 − (−1)) = −8 / 4 = **−2**

The slope is negative, which makes sense because the y-values dropped (4 → −4) as we moved right.""",
        3,
    ),
    (
        "Slope-intercept form",
        """## The most common form

If a line has slope *m* and crosses the y-axis at y = *b*, its equation can be written as:

> y = m x + b

This is **slope-intercept form**. The *m* is the slope; the *b* is the y-intercept — the y-value where the line
crosses the vertical axis. Every linear equation can be rewritten in this form, and once it's there, you can
read both key facts off the equation.

## Reading it

- **y = 3x + 2**: slope 3, y-intercept 2. Starts at (0, 2), rises 3 for every 1 to the right.
- **y = −x + 5**: slope −1, y-intercept 5. Starts at (0, 5), drops 1 for every 1 to the right.
- **y = (1/2)x**: slope 1/2, y-intercept 0. Passes through the origin, gentle climb.

## Graphing from slope-intercept

Two steps, every time:

1. Plot the y-intercept: mark the point (0, b).
2. Use the slope to get a second point: from (0, b), go *run* right and *rise* up (down if negative).

That's it. Two points, draw a line through them, and extend it to the edges of your graph. With practice this
should take under fifteen seconds.""",
        4,
    ),
    (
        "Interpreting slope in context",
        """## Units and meaning

A slope is never just a number; it always has units that match the axes. When you report a slope in a real-world
problem, include the units or you have not finished the problem.

## Example — a savings account

A savings account starts at $200 and grows by $15 per week. On a graph with weeks on the x-axis and dollars on
the y-axis, the line has y-intercept 200 and slope 15 **dollars per week**. The equation is:

> y = 15x + 200

The slope answers "how fast is the balance growing?" — $15 every week. The y-intercept answers "how much was
there at week 0?" — $200.

## Example — a road trip

You leave home at time t = 0 and drive at 60 miles per hour. Distance from home on the y-axis, time on the
x-axis. Slope = 60 mi/hr. Intercept = 0 (you start at home).

## The interpretation habit

For any linear graph, ask yourself three questions:

1. What does an increase of 1 on the x-axis mean in the real world?
2. What does the slope tell me about how fast y changes per unit of x?
3. What does the y-intercept tell me about where y starts?

If you can answer those in plain English, you've understood the line.""",
        5,
    ),
    (
        "Common mistakes with slope",
        """## Mistake 1 — flipping rise and run

Slope is rise over run, not run over rise. A line that goes up 1 and right 4 has slope 1/4, not 4. Memorize the
picture: the number on top is "how much up," the number on bottom is "how much over."

## Mistake 2 — inconsistent subtraction order

Using (y₂ − y₁) on top but (x₁ − x₂) on bottom gives you the *wrong sign*. Either subtract second-minus-first
in both, or first-minus-second in both.

## Mistake 3 — confusing intercepts

The y-intercept is where the line meets the **y-axis** (x = 0), not the x-axis. Students sometimes plug the
x-intercept into slope-intercept form and wonder why their graph is wrong.

## Mistake 4 — treating vertical lines as "slope = infinity"

Vertical lines have slope **undefined**, not infinity. The distinction matters because "undefined" means "the
formula does not apply here," not "a very large number."

## Mistake 5 — forgetting the units

A slope of "20" tells you nothing without units. Is it dollars per hour? Miles per minute? Always carry the units
through the answer.""",
        6,
    ),
    (
        "Checkpoint before the quiz",
        """## Quick recap

- Slope = rise / run = Δy / Δx.
- Two-point formula: m = (y₂ − y₁) / (x₂ − x₁). Be consistent with the subtraction order.
- Slope-intercept form: y = m x + b, where b is the y-intercept and m is the slope.
- Flat lines: slope 0. Vertical lines: slope undefined.
- Always attach units to slope in a real-world problem.

## Self-test

Try these in your head before the quiz:

- A line passes through (0, 3) and (4, 11). What is the slope?
- A line has equation y = −2x + 7. Where does it cross the y-axis?
- If a coffee shop's earnings rise $120 per day and it started at $0, write the equation.

Answers: 2; (0, 7); y = 120x.

## What's next

The next lesson is **Systems of Linear Equations** — where two lines meet, how to find that point, and why the
meeting point is the answer to many everyday questions. If you feel solid on slope, you're ready.""",
        7,
    ),
]

_LESSON_C_QUESTIONS = [
    (
        "What is the slope of a line through (1, 2) and (4, 11)?",
        ["3", "1/3", "9", "−3"],
        "3",
    ),
    (
        "In y = −4x + 9, what is the y-intercept?",
        ["−4", "4", "9", "−9"],
        "9",
    ),
    (
        "Which line is horizontal?",
        ["y = 5", "x = 5", "y = 5x", "y = x + 5"],
        "y = 5",
    ),
    (
        "If a car's distance increases 55 miles per hour, what is the slope on a time-vs-distance graph?",
        ["55 miles per hour", "55 hours per mile", "55 miles", "1/55"],
        "55 miles per hour",
    ),
]


_LESSON_D_SECTIONS = [
    (
        "What a system of equations is",
        """## Two lines, one question

A **system of linear equations** is a set of two or more linear equations that we want to solve at the same
time. The solution is the (x, y) pair — or pairs — that makes every equation in the system true. Geometrically,
each equation is a line on the plane, and the solution is the point (or points) where the lines meet.

Why do we care? Because many real problems naturally split into two simultaneous conditions. "I have $20 and I
bought apples at $2 each and bananas at $0.50 each, totaling 8 pieces of fruit — how many of each?" That's two
equations: one for the total cost, one for the total number. The answer is the single (apples, bananas) pair
that satisfies both at once.

## Three possible outcomes

Two lines on a plane can relate in exactly three ways:

- They **cross once** — one unique solution, a single (x, y).
- They are **parallel and distinct** — no solution; the system is *inconsistent*.
- They are **the same line** (one is a multiple of the other) — infinite solutions; the system is *dependent*.

Understanding which category your system falls into is half of solving it. The other half is finding the
solution when it exists. This lesson covers the two standard methods: **substitution** and **elimination**.""",
        0,
    ),
    (
        "Method 1: substitution",
        """## The core move

Substitution works when one equation is already solved for a variable — or can be quickly rearranged to be.
The plan is:

1. Solve one equation for one variable (say, y).
2. Substitute that expression into the *other* equation.
3. Now you have one equation in one variable — solve it normally.
4. Plug that value back into either original equation to find the other variable.

## Worked example

Solve:

```
y = 2x + 1
3x + y = 11
```

The first equation is already solved for y. Substitute `2x + 1` into the second:

```
3x + (2x + 1) = 11
5x + 1 = 11
5x = 10
x = 2
```

Plug x = 2 back into y = 2x + 1: y = 2·2 + 1 = **5**. So the solution is (2, 5).

Check: does (2, 5) satisfy both equations? 5 = 2·2 + 1 ✓. And 3·2 + 5 = 11 ✓. Both hold, so we're done.""",
        1,
    ),
    (
        "Watch: solving systems step by step",
        "YT::vA-55wZtLeE::Khan Academy walks through substitution and elimination with clear narration.",
        2,
    ),
    (
        "Method 2: elimination",
        """## The core move

Elimination works when the equations are in the form `Ax + By = C`. You add or subtract the equations to *cancel
out* one variable, leaving a single-variable equation. Sometimes you first multiply one or both equations by a
constant to make the coefficients line up.

## Worked example — straight add

Solve:

```
 2x + 3y = 12
−2x + 5y =  4
```

The x-coefficients are already opposites. Add the equations term by term:

```
(2x − 2x) + (3y + 5y) = 12 + 4
0 + 8y = 16
y = 2
```

Plug y = 2 back into either equation: 2x + 3·2 = 12 → 2x = 6 → x = **3**. Solution: (3, 2).

## Worked example — scale first

Solve:

```
3x + 4y = 18
 x + 2y =  8
```

Multiply the second equation by −3 so the x-coefficients become opposites:

```
 3x + 4y = 18
−3x − 6y = −24
```

Add: `−2y = −6`, so y = **3**. Plug into x + 2y = 8: x = 8 − 6 = **2**. Solution: (2, 3).

## Picking the method

- Substitution is easy when one variable is already isolated.
- Elimination is easy when both equations are in Ax + By = C form, especially if the coefficients line up.

Both always give the same answer on a solvable system. Use whichever is less work.""",
        3,
    ),
    (
        "No solution and infinite solutions",
        """## When the lines never meet

If while solving you reach a statement like `0 = 5` (a false statement with no variables), the system has **no
solution** — the lines are parallel. Example:

```
y = 2x + 1
y = 2x − 3
```

Same slope, different intercepts → parallel, never cross.

## When the lines are the same

If you reach something like `0 = 0` (a true statement with no variables), the system has **infinite
solutions** — the two equations describe the same line. Example:

```
 2x + 4y =  6
 x + 2y =  3
```

Multiply the second by 2: `2x + 4y = 6` — identical to the first. Any (x, y) on that line works.

## The workflow

While solving, if the variable disappears:

- False statement → parallel lines, no solution.
- True statement → same line, infinite solutions.

If the variable *does not* disappear, you'll get a clean (x, y) and should check it.""",
        4,
    ),
    (
        "A word problem, start to finish",
        """## Setup

A coffee shop sells muffins for $3 and cookies for $2. On a slow afternoon they sell a total of 20 items and
take in $52. How many of each did they sell?

## Translate

Let *m* = muffins and *c* = cookies. The conditions become two equations:

```
m + c = 20      (total items)
3m + 2c = 52    (total revenue)
```

## Solve

This is a perfect fit for elimination. Multiply the first equation by −2:

```
−2m − 2c = −40
 3m + 2c =  52
```

Add: `m = 12`. So they sold **12 muffins**. Plug back into the first equation: `12 + c = 20`, so
`c = 8`. **8 cookies.**

## Check

12 + 8 = 20 items ✓. 3·12 + 2·8 = 36 + 16 = 52 dollars ✓. Both hold — the answer is right.

## The takeaway

Word problems become systems whenever you have two unknowns and two independent conditions. Nearly every
mixture, rate, or age problem in the textbook follows this pattern.""",
        5,
    ),
    (
        "Common mistakes with systems",
        """## Mistake 1 — sloppy substitution

When substituting an expression for a variable, wrap it in parentheses before plugging in. `3x + (2x + 1)`
carries the +1 correctly. `3x + 2x + 1` happens to work here, but in `3x − (2x + 1)`, dropping the parentheses
flips your sign error waiting to happen.

## Mistake 2 — multiplying only part of an equation

When you scale an equation, you must scale *every* term. Going from `x + 2y = 8` to `3x + 2y = 24` is wrong; the
correct scaling is `3x + 6y = 24`.

## Mistake 3 — only checking one equation

A solution has to satisfy *both* equations. Plug it into the one you didn't use to isolate the variable — that's
often where an arithmetic slip shows up.

## Mistake 4 — confusing "no solution" with "zero"

If you end up with `0 = 0`, the answer is **infinite solutions**, not "x = 0" and not "no solution." If you end
up with `0 = 5`, the answer is **no solution** — a statement about the system, not a value of x.

## Mistake 5 — forgetting to find both variables

Finding x = 3 is half the problem. The solution is an (x, y) pair, so always plug back in to find y (or vice
versa) before you call it done.""",
        6,
    ),
    (
        "Checkpoint before the quiz",
        """## Quick recap

- A system of linear equations asks for the (x, y) pair that satisfies all the equations simultaneously.
- **Substitution**: isolate one variable, plug into the other equation.
- **Elimination**: add or subtract equations (after scaling if needed) to cancel a variable.
- `0 = 5` means no solution (parallel lines). `0 = 0` means infinite solutions (same line).
- Always check your answer in *both* equations.

## Self-test

Without looking back, work these:

- Solve: y = x + 1 and y = 2x − 1.
- Solve: 2x + y = 7 and x − y = 2.
- Without solving, how many solutions does y = 3x + 4 and y = 3x − 7 have?

Answers: (2, 3); (3, 1); none (parallel).

## What's next

The next lesson covers **polynomial basics** — multiplying and factoring small polynomials. Systems of equations
will come back when we start graphing parabolas, so the intuition you built here carries forward.""",
        7,
    ),
]

_LESSON_D_QUESTIONS = [
    (
        "Solve the system: y = x + 2 and y = 2x − 1.",
        ["(3, 5)", "(1, 3)", "(2, 4)", "(0, 2)"],
        "(3, 5)",
    ),
    (
        "While solving a system you reach 0 = 7. What does this mean?",
        ["Infinite solutions", "The solution is zero", "No solution (parallel lines)", "You divided by zero"],
        "No solution (parallel lines)",
    ),
    (
        "Which method works best when one equation is y = something in terms of x?",
        ["Substitution", "Elimination", "Graphing only", "Guess and check"],
        "Substitution",
    ),
    (
        "For the system 2x + y = 6 and x − y = 0, what is x?",
        ["2", "3", "4", "6"],
        "2",
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
    await _ensure_seed_lesson(
        db,
        class_id=cls.id,
        title=SEED_LESSON_C_TITLE,
        order_index=2,
        sections=_LESSON_C_SECTIONS,
        questions=_LESSON_C_QUESTIONS,
    )
    await _ensure_seed_lesson(
        db,
        class_id=cls.id,
        title=SEED_LESSON_D_TITLE,
        order_index=3,
        sections=_LESSON_D_SECTIONS,
        questions=_LESSON_D_QUESTIONS,
    )

    # Filler classes — no materials, student is pre-enrolled so the dashboard
    # has real texture instead of a single card.
    for spec in SEED_FILLER_CLASSES:
        filler = await db.scalar(select(Class).where(Class.enrollment_code == spec["code"]))
        if filler is None:
            filler = Class(
                educator_id=educator.id,
                title=spec["title"],
                description=spec["description"],
                enrollment_code=spec["code"],
            )
            db.add(filler)
            await db.flush()
        already_enrolled = await db.scalar(
            select(Enrollment.id).where(
                Enrollment.class_id == filler.id, Enrollment.student_id == student.id
            )
        )
        if not already_enrolled:
            db.add(Enrollment(class_id=filler.id, student_id=student.id))

    await db.commit()
    await _ensure_seed_student_activity(db, student_id=student.id, class_id=cls.id)


# ------------------------------------------------------------------
# Simulated student history for the seed student so the UI renders
# with real content instead of empty-state placeholders.
# ------------------------------------------------------------------


_SEED_FEATURE_PROFILES: dict[str, dict] = {
    # Lesson A — geometry/pythagorean: lots of hovering and diagram gazing
    "A_focused": {
        "total_time_s": 260, "hover_count": 7, "avg_hover_duration_ms": 1100,
        "scroll_depth_pct": 98, "back_scroll_count": 3, "scroll_velocity_avg": 0.35,
        "mouse_velocity_avg": 0.28, "mouse_velocity_variance": 4.0,
        "idle_total_s": 6, "idle_count": 1, "text_selection_count": 4,
        "re_read_sections": ["1", "3"], "reading_speed_wpm": 175, "section_completion_rate": 1.0,
    },
    "A_loose": {
        "total_time_s": 140, "hover_count": 2, "avg_hover_duration_ms": 380,
        "scroll_depth_pct": 62, "back_scroll_count": 9, "scroll_velocity_avg": 1.5,
        "mouse_velocity_avg": 2.4, "mouse_velocity_variance": 210,
        "idle_total_s": 58, "idle_count": 4, "text_selection_count": 0,
        "re_read_sections": [], "reading_speed_wpm": 115, "section_completion_rate": 0.5,
    },
    # Lesson B — solving equations: reads faster, fewer hovers, more selections
    "B_focused": {
        "total_time_s": 210, "hover_count": 3, "avg_hover_duration_ms": 600,
        "scroll_depth_pct": 96, "back_scroll_count": 2, "scroll_velocity_avg": 0.5,
        "mouse_velocity_avg": 0.35, "mouse_velocity_variance": 6.0,
        "idle_total_s": 8, "idle_count": 1, "text_selection_count": 6,
        "re_read_sections": ["0"], "reading_speed_wpm": 215, "section_completion_rate": 1.0,
    },
    "B_loose": {
        "total_time_s": 120, "hover_count": 1, "avg_hover_duration_ms": 220,
        "scroll_depth_pct": 55, "back_scroll_count": 6, "scroll_velocity_avg": 1.2,
        "mouse_velocity_avg": 1.8, "mouse_velocity_variance": 160,
        "idle_total_s": 42, "idle_count": 3, "text_selection_count": 0,
        "re_read_sections": [], "reading_speed_wpm": 145, "section_completion_rate": 0.6,
    },
    # Lesson C — slope & graphs: heavy visual focus, lots of scroll activity
    "C_focused": {
        "total_time_s": 280, "hover_count": 9, "avg_hover_duration_ms": 1350,
        "scroll_depth_pct": 99, "back_scroll_count": 5, "scroll_velocity_avg": 0.6,
        "mouse_velocity_avg": 0.45, "mouse_velocity_variance": 9.0,
        "idle_total_s": 5, "idle_count": 1, "text_selection_count": 2,
        "re_read_sections": ["2"], "reading_speed_wpm": 165, "section_completion_rate": 1.0,
    },
    "C_loose": {
        "total_time_s": 170, "hover_count": 3, "avg_hover_duration_ms": 520,
        "scroll_depth_pct": 68, "back_scroll_count": 11, "scroll_velocity_avg": 1.1,
        "mouse_velocity_avg": 1.6, "mouse_velocity_variance": 140,
        "idle_total_s": 38, "idle_count": 3, "text_selection_count": 1,
        "re_read_sections": [], "reading_speed_wpm": 135, "section_completion_rate": 0.7,
    },
    # Lesson D — systems of equations: longer sessions, more re-reads
    "D_focused": {
        "total_time_s": 320, "hover_count": 5, "avg_hover_duration_ms": 780,
        "scroll_depth_pct": 97, "back_scroll_count": 6, "scroll_velocity_avg": 0.5,
        "mouse_velocity_avg": 0.4, "mouse_velocity_variance": 7.5,
        "idle_total_s": 10, "idle_count": 1, "text_selection_count": 4,
        "re_read_sections": ["1", "2"], "reading_speed_wpm": 155, "section_completion_rate": 1.0,
    },
    "D_loose": {
        "total_time_s": 180, "hover_count": 2, "avg_hover_duration_ms": 420,
        "scroll_depth_pct": 70, "back_scroll_count": 14, "scroll_velocity_avg": 1.0,
        "mouse_velocity_avg": 1.9, "mouse_velocity_variance": 190,
        "idle_total_s": 48, "idle_count": 3, "text_selection_count": 0,
        "re_read_sections": [], "reading_speed_wpm": 125, "section_completion_rate": 0.65,
    },
}


def _seed_features(*, focused: bool, word_count: int, tag: str = "A") -> dict:
    """Per-lesson plausible feature dict. Tags: A/B/C/D map to the 4 algebra lessons."""
    key = f"{tag}_{'focused' if focused else 'loose'}"
    template = _SEED_FEATURE_PROFILES.get(key) or _SEED_FEATURE_PROFILES["A_focused"]
    return {
        "time_per_section": {},
        "hover_per_section": {},
        **template,
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
    # Cover all four algebra lessons with distinct feature profiles so the
    # researcher workbench renders noticeably different telemetry per lesson.
    pattern = [
        ("A", True, 10),   # lesson A — 10 days ago, focused
        ("A", False, 9),   # lesson A — shakier revisit
        ("B", False, 7),   # lesson B — distracted first pass
        ("B", True, 6),    # lesson B — second pass clean
        ("C", False, 4),   # lesson C — first pass loose
        ("C", True, 3),    # lesson C — focused rerun
        ("D", False, 2),   # lesson D — first pass shakier
        ("D", True, 1),    # lesson D — focused, most recent
    ]
    lesson_by_tag: dict[str, Material] = {}
    for i, tag in enumerate(["A", "B", "C", "D"]):
        if i < len(materials):
            lesson_by_tag[tag] = materials[i]
        else:
            lesson_by_tag[tag] = materials[-1]

    score_pattern = [0.62, 0.55, 0.58, 0.72, 0.65, 0.82, 0.74, 0.88]

    for index, (tag, focused, days_ago) in enumerate(pattern):
        material = lesson_by_tag[tag]
        sections = list(material.sections)
        questions = list(material.questions)
        word_count = sum(s.word_count for s in sections) or 400

        started = now - timedelta(days=days_ago, minutes=5)
        ended = started + timedelta(minutes=5 if focused else 3)
        features = _seed_features(focused=focused, word_count=word_count, tag=tag)
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

