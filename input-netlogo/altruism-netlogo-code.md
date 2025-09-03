patches-own [
  benefit-out                 ;; 1 for altruists, 0 for selfish
  altruism-benefit
  fitness
  self-weight self-fitness
  alt-weight alt-fitness
  harsh-weight harsh-fitness
]

to setup
  clear-all
  ask patches [ initialize ]
  reset-ticks
end

to initialize  ;; patch procedure
  let ptype random-float 1.0
  ifelse (ptype < altruistic-probability) [
    set benefit-out 1
    set pcolor pink
  ] [
    set benefit-out 0
    ifelse (ptype < altruistic-probability + selfish-probability) [
      set pcolor green
    ] [
      set pcolor black
    ]
  ]
end

to go
  ;; if all altruistic and selfish patches are gone, stop
  if all? patches [pcolor != pink and pcolor != green]
    [ stop ]
  ask patches [
    set altruism-benefit   benefit-from-altruism * (benefit-out + sum [benefit-out] of neighbors4) / 5
  ]
  ask patches [
    perform-fitness-check
  ]
  lottery
  tick
end

to perform-fitness-check  ;; patch procedure
  if (pcolor = green) [
    set fitness (1 + altruism-benefit)
  ]
  if(pcolor = pink) [
    set fitness ((1 - cost-of-altruism) + altruism-benefit)
  ]
  if (pcolor = black) [
    set fitness harshness
  ]
end

to lottery
  ask patches [ record-neighbor-fitness ]
  ask patches [ find-lottery-weights ]
  ask patches [ next-generation ]
end

to record-neighbor-fitness  ;; patch procedure
  set alt-fitness 0
  set self-fitness 0
  set harsh-fitness 0
  if (pcolor = pink) [
    set alt-fitness fitness
  ]
  if (pcolor = green) [
    set self-fitness fitness
  ]
  if (pcolor = black) [
    set harsh-fitness fitness
  ]
  update-fitness-from-neighbor 1 0
  update-fitness-from-neighbor -1 0
  update-fitness-from-neighbor 0 1
  update-fitness-from-neighbor 0 -1
end

to update-fitness-from-neighbor [x y]  ;; patch procedure
  let neighbor-color [pcolor] of patch-at x y
  let neighbor-fitness [fitness] of patch-at x y
  if (neighbor-color = pink)
    [set alt-fitness (alt-fitness + neighbor-fitness)]
  if (neighbor-color = green)
    [set self-fitness (self-fitness + neighbor-fitness)]
  if(neighbor-color = black)
    [set harsh-fitness (harsh-fitness + neighbor-fitness)]
end

to find-lottery-weights ;; patch procedure
  let fitness-sum alt-fitness + self-fitness + harsh-fitness + disease
  ifelse (fitness-sum > 0) [
    set alt-weight (alt-fitness / fitness-sum)
    set self-weight (self-fitness / fitness-sum)
    set harsh-weight ((harsh-fitness + disease) / fitness-sum)
  ] [
    set alt-weight 0
    set self-weight 0
    set harsh-weight 0
  ]
end

to next-generation ;; patch procedure
  let breed-chance random-float 1.0
  ifelse (breed-chance < alt-weight) [
    set pcolor pink
    set benefit-out 1
  ] [
    ifelse (breed-chance < (alt-weight + self-weight))[
      set pcolor green
      set benefit-out 0
    ] [
      clear-patch
    ]
  ]
end

to clear-patch ;; patch procedure
  set pcolor black
  set altruism-benefit 0
  set fitness 0
  set alt-weight 0
  set self-weight 0
  set harsh-weight 0
  set alt-fitness 0
  set self-fitness 0
  set harsh-fitness 0
  set benefit-out 0
end


; Copyright 1998 Uri Wilensky.
; See Info tab for full copyright and license.