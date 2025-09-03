globals [
  target     ; the target line in the middle
  max-dist   ; the maximum distance to that wall
  attempts   ; the number of attempts made so far with the current strategy

  ; lists of each run's distance halfway through the run's attempts
  p-results
  v-results
  pv-results
  r-results
]

turtles-own [
  max-moves      ; the max-moves of the current throw
  best-max-moves ; the best throw of the agent (or, if no memory, the current throw)
  moves-left     ; the number of moves left until the ball comes to rest
  score          ; the current score (how far from target... lower is better)
  best-score     ; best score (or, if no memory, current throw)
]

to setup
  clear-all

  ; the target is the line in the center of the screen, one patch thick
  set target patches with [ pxcor = 0 ]

  set-default-shape turtles "circle-arrow"
  set max-dist world-width

  create-turtles number-of-players [
    set size (world-height / number-of-players)
    set color color + 0.1 ; to make trails a little easier to see
  ]
  spread-out-turtles-evenly

  ; initialize result lists
  set p-results  []
  set v-results  []
  set pv-results []
  set r-results  []

  setup-run
  setup-attempt
  reset-ticks
end

to spread-out-turtles-evenly
  let d (world-height / count turtles)
  let y (min-pycor - 0.5 + (d / 2))
  foreach sort turtles [ t ->
    ask t [ set ycor round y ]
    set y (y + d)
  ]
end

to setup-run
  set attempts 0
  ; random strategies lets you keep the simulation running
  ; picking from the available strategies at random
  if randomize-strategy-each-run? [
    set strategy one-of [ "Random" "Piagetian" "Vygotskiian" "P-V" ]
  ]
  ask turtles [
    set score (max-dist + 1) ; start with a dummy score that is sure to be beaten
    set best-score score
    ; their max-moves are randomly distributed over the length of the playing field
    set max-moves random max-dist
  ]
end

to-report get-strategy-color
  if strategy = "Random"      [ report green ]
  if strategy = "Piagetian"   [ report blue  ]
  if strategy = "Vygotskiian" [ report red   ]
  if strategy = "P-V"         [ report grey  ]
end

to setup-attempt
  clear-patches
  ask target [
    set pcolor get-strategy-color
  ]
  ; place turtles at starting line
  ask turtles [
    set heading 90
    set xcor min-pxcor
  ]
end

to go

  if attempts >= attempts-per-run [ setup-run ]
  setup-attempt

  ; move all the turtles forward to their max-moves spot
  move-turtles

  ; the score is their distance from the target line
  ask turtles [ set score distancexy 0 ycor ]

  ; act according to the strategy, e.g,. in Vygotskiian, you compare
  ; your scores to a neighbor and possibly update your score
  ask turtles [ adjust ]

  set attempts (attempts + 1)
  if attempts = round (attempts-per-run / 2) [ record-result ]
  tick
  if attempts >= attempts-per-run and stop-after-each-run? [
    stop
  ]

end

to move-turtles
  ; move all the turtles forward to their max-moves spot.
  ; we can't just say "forward max-moves" because we want
  ; them to bounce off the wall and leave a dissipating trail
  ask turtles [ set moves-left limit-legal-distance max-moves ]
  let moving-turtles turtles with [ moves-left > 0 ]
  while [ any? moving-turtles ] [
    set moving-turtles turtles with [ moves-left > 0 ]
    ask moving-turtles [
      move-x
      if trails? [
        set pcolor (color - 5) + (10 * (max-moves - moves-left) / max-moves)
      ]
    ]
  ]
end

to record-result
  let current-mean mean [ score ] of turtles
  if strategy = "Random"      [ set  r-results lput current-mean  r-results ]
  if strategy = "Piagetian"   [ set  p-results lput current-mean  p-results ]
  if strategy = "Vygotskiian" [ set  v-results lput current-mean  v-results ]
  if strategy = "P-V"         [ set pv-results lput current-mean pv-results ]
end

to move-x
  set moves-left moves-left - 1
  forward 1
  if pxcor >= (max-pxcor - 1) [
    set heading 270
    forward 2
  ]
end

to-report limit-legal-distance [ val ]
  report min (list (max-dist - 1) max (list 0 val))
end

to adjust
  if strategy = "Random" [
    r-adjust
    set max-moves best-max-moves
    stop
  ]
  if strategy = "Piagetian" [ p-adjust ]
  if strategy = "Vygotskiian" [ v-adjust ]
  if strategy = "P-V" [ pv-adjust ]

  if strategy = "Vygotskiian" [
    set max-moves limit-legal-distance
      (best-max-moves + (random-normal 0 (move-error * best-score / max-dist)))
    stop
  ]

  ifelse xcor > 0 [
    set max-moves limit-legal-distance
      (best-max-moves +  (- abs random-normal 0 (move-error * best-score / max-dist)))
  ] [
    set max-moves limit-legal-distance
      (best-max-moves + (abs random-normal 0 (move-error * best-score / max-dist)))
  ]
end

to p-adjust
  ; if your score is better, that's your new best, otherwise stick with the old
  if score < best-score [ ; note that lower scores are better (closer to target line)
    set best-score score
    set best-max-moves max-moves
  ]
end

to v-adjust
  let fellow nobody
  while [ fellow = nobody or fellow = self ] [
    set fellow turtle (who + (- (#-vygotskiian-neighbors / 2)) + random (1 + #-vygotskiian-neighbors))
  ]
  ; look randomly to one of your neighbors

  ; if the score is better and it is within your ZPD, use their max-moves.
  ifelse (best-score > [ best-score ] of fellow) and (best-score - ZPD <= [ best-score ] of fellow) [
    set best-score [ best-score ] of fellow
    set best-max-moves [ best-max-moves ] of fellow
  ]
  [
    set best-score score
    set best-max-moves max-moves
  ]
end

to pv-adjust

  ; look randomly to one of your neighbors
  let fellow nobody
  while [ fellow = nobody or fellow = self ] [
    set fellow turtle (who + (- (#-vygotskiian-neighbors / 2)) + random (1 + #-vygotskiian-neighbors))
  ]

  ; maximize your own score and...
  if score < best-score [
    set best-score score
    set best-max-moves max-moves
  ]

  ; check it against your neighbor's score
  if (best-score > [ best-score ] of fellow) and (best-score - ZPD <= [ best-score ] of fellow) [
    set best-score [ best-score ] of fellow
    set best-max-moves [ best-max-moves ] of fellow
  ]
end

to r-adjust
  ; random strategy changes max-moves to a random number x if it's not at the wall
  ; where 0 < x < max-dist
  ; if it is at the target, it stops changing.
  ifelse abs pxcor > 0 [
    set best-max-moves (random max-dist)
  ] [
    set best-max-moves (max-dist / 2) - 1
  ]
end


; Copyright 2005 Uri Wilensky.
; See Info tab for full copyright and license.