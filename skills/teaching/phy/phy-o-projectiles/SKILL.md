---
name: phy-o-projectiles
kind: teaching
version: "0.1"
status: draft
language: en
summary: Teach projectile motion by splitting the launch velocity into two parts
description: "Projectile motion, components of velocity, time of flight, maximum height and range: resolve the launch velocity, treat the vertical motion with g and the horizontal motion as constant, then combine them. Not for: straight-line motion (phy-o-motion) or the forces on a moving object (phy-o-forces)."
subject: physics
levels: [O]
topics: [projectile motion, projectiles, components of velocity, time of flight, maximum height, range, launch angle, trajectory]
kcs:
  - kc.phy.o.projectiles.resolve
  - kc.phy.o.projectiles.components_change
  - kc.phy.o.projectiles.trajectory_graphs
  - kc.phy.o.projectiles.time_of_flight
  - kc.phy.o.projectiles.max_height
  - kc.phy.o.projectiles.range
curriculum_refs: [PHY-O-01.09]
prerequisites: [kc.phy.o.motion.free_fall, kc.phy.o.measurement.scalars_and_vectors]
related: [phy-o-motion, phy-o-forces, phy-o-measurement]
pedagogy: [pedagogy-guided-solve]
audience: student
roles: [coach, diagnoser, solver, checker]
requires_tools: [math_evaluate, phys_projectile, units_check_dimensions]
visuals: [projectile_sim, motion_graph]
answer_policy:
  mode: withhold_until_earned
  min_attempts: 1
escalation:
  after_failed_attempts: 3
  action: prerequisite_detour
plausibility:
  - quantity: speed
    unit: m/s
    min: 0
    max: 60
    context: balls and stones thrown or kicked by a person
  - quantity: height
    unit: m
    min: 0
    max: 50
    context: the highest point of a thrown or kicked object
  - quantity: time
    unit: s
    min: 0
    max: 10
    context: the time a thrown or kicked object stays in the air
  - quantity: distance
    unit: m
    min: 0
    max: 200
    context: the range of a thrown or kicked object on level ground
owner: physics-lead
last_reviewed_by: not-yet-reviewed
last_reviewed_at: "2026-10-31"
success_criteria:
  - The student writes the horizontal and vertical components of the launch velocity with units before anything else
  - The student says which component gravity changes and which stays constant, and uses only the vertical one for times and heights
  - The student reaches a checked time of flight, maximum height or range with a correct unit
---

# Projectile motion

## When to use

Use when a problem launches an object at an angle above the ground, or sideways from a height, and asks for the
horizontal or vertical component of its velocity, its time of flight, its maximum height, its range, or the shape of
its path or its motion graphs. Air resistance is ignored, as at this level.

Not for: motion along one straight line, including objects thrown straight up (phy-o-motion), or questions about
the forces on a moving object (phy-o-forces).

## What this skill does not do

- It does not treat air resistance or drag; every path is a parabola.
- It does not use calculus; components come from a right-angled triangle and the equations of uniform acceleration.
- It does not choose the value of g: the question or the pack convention gives it.

## Objectives

1. The student writes the horizontal and vertical components of the launch velocity with units before anything else.
2. The student says which component gravity changes and which stays constant, and uses only the vertical one for times and heights.
3. The student reaches a checked time of flight, maximum height or range with a correct unit.

## Prerequisite probe

- "A ball is thrown straight up at 12 m/s. Take g = 10 m/s². How long does it take to reach the top?" Expected: 1.2 s (checked with math_evaluate).
- "A force of 10 N acts at 30° above the horizontal. What is its horizontal part?" Expected: 8.66 N (checked with math_evaluate).

If the first fails, step back to free fall in phy-o-motion; if the second fails, step back to resolving a vector into two parts, then return to this problem.

## Teaching sequence

1. Ask the student to draw the launch velocity as the slanted side of a right-angled triangle and label the launch angle. Done when the triangle is on the board with the angle marked.
2. Ask for the horizontal component u cos θ and the vertical component u sin θ, each with a unit. Done when both components are written and checked.
3. Ask which component gravity changes. Done when the student says the vertical one changes by g each second and the horizontal one stays constant.
4. Ask the student to work on the vertical motion alone: time to the top from u_y ÷ g, time of flight from doubling it, or maximum height from u_y² ÷ 2g. Done when the vertical quantity the question needs is written and checked.
5. Ask the student to combine the two motions for the range: horizontal velocity times time of flight. Done when the range matches the checked value.
6. Ask for the unit and a sense check against a real throw or kick. Done when the unit passes units_check_dimensions and the value is sensible.

## Hint ladder

1. Orient: "Which direction does the question ask about: along the ground, straight up, or both?"
2. Concept: name the idea in words, such as "gravity changes only the vertical part of the velocity" or "the range is the horizontal velocity times the time in the air".
3. First step: write the relation with symbols, such as T = 2 u sin θ ÷ g, and ask the student to put the numbers in.
4. Worked step: show the substitution and ask the student for the value.
5. Full step: show the checked result; the step counts as not mastered and a similar item is scheduled.

## Misconceptions

- `mc.phy.o.components_swapped`: uses u sin θ for the horizontal component → "Which side of your triangle is next to the angle, and which is opposite it?"
- `mc.phy.o.horizontal_velocity_slows`: lets the horizontal velocity die away during the flight → "What pushes or pulls the ball sideways once it has left the foot?"
- `mc.phy.o.flight_time_is_time_to_top`: gives the time to the top as the time of flight → "Where is the ball when the clock stops: at the top, or back on the ground?"
- `mc.phy.o.range_taken_as_height`: gives the maximum height when asked for the range → "Is the question asking how far along the ground, or how high up?"
- `mc.phy.o.steeper_launch_goes_further`: expects a steeper launch at the same speed to land further → "A steeper launch stays up longer, but what happens to its sideways speed?"

## Confidence and escalation

- Two failures on the components: redraw the triangle and ask which side is next to the angle before any numbers.
- Three failures on the vertical motion: detour to free fall in phy-o-motion, then return.
- A range that is about half the checked value: treat it as mc.phy.o.horizontal_velocity_slows or a missing doubling of the time, and ask which before correcting.

## Worked exchange

> Tutor: A ball is kicked from level ground at 20 m/s at 30° above the horizontal. Take g = 10 m/s². How far away does it land? What are the two parts of the launch velocity?
> Student: Horizontal is 20 cos 30°, which is 17.3 m/s, and vertical is 20 sin 30°, which is 10 m/s.
> Tutor: Both right (checked with the maths tool). Which of those does gravity change?
> Student: The vertical one. It goes to zero at the top, so the way up takes 10 ÷ 10 = 1 s and the whole flight takes 2 s.
> Tutor: Good. Now how far does the ball move sideways in those 2 s?
> Student: 17.3 × 2 = 34.6 m.
> Tutor: That matches the checked value, and 34.6 m is a sensible kick.

## Verification checklist

- Every number shown comes from the question or has a check from math_evaluate or phys_projectile.
- The final unit passed units_check_dimensions.
- The time of flight is the whole flight, not the time to the top, unless the question asks for the top.
- The horizontal velocity used for the range is the launch value, unchanged.

## Reference relations

For a launch at speed u and angle θ above level ground, with g the acceleration of free fall and air resistance
ignored. These authored relations let the worker check a student's symbolic formula even when the hidden solution
plan starts with substitution.

- `u_x = u*cos(theta)`
- `u_y = u*sin(theta)`
- `T = 2*u*sin(theta)/g`
- `H = (u*sin(theta))^2/(2*g)`
- `R = u^2*sin(2*theta)/g`
