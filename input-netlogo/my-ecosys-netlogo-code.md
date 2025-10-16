;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
;;;;;;;;;;;;;;; INIT ;;;;;;;;;;;;;;;;;  
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
  
globals [  
  ;; global constants  
  INITIAL-YEAR  
  MONTH-NAMES  
  RAIN-LIGHT  
  RAIN-MODERATE  
  RAIN-HEAVY  
  RAIN-EXTREME  
  TOWN-HALL-NEXT-ELECTION  
  
  ;; global variables  
  current-date-full-int  
  current-date-full-string  
  current-day  
  current-month  
  current-year  
  forest-water-retention  
  hpc-computing-load  
  hpc-water-rejection-temperature  
  rain-amount  
  rain-intensity  
  restoration-duration  
  river-level-current  
  river-level-previous  
  river-temperature  
  total-current-rain  
  town-hall-budget  
]  
  
;; specification of breeds , i.e. types of agents (subtype of turtle)  
breed [waves wave]  
breed [raindrops raindrop]  
raindrops-own [ quantity is-new?] ;; attributes of raindrops  
breed [plants plant]  
breed [trees tree]  
breed [hpcs hpc]  
  
;; size of the grid is [-16; 16]  
;; constants initialization  
to initialize-constants  
  set MONTH-NAMES ["January" "February" "March" "April" "May" "June" "July" "August" "September" "October" "November" "December"]  
  set INITIAL-YEAR 2025  
  set TOWN-HALL-NEXT-ELECTION 6 * 365  
  
  ;; typical values in mm per hour for Luxembourg  
  set RAIN-LIGHT 0.5  
  set RAIN-MODERATE 3  
  set RAIN-HEAVY 10  
  set RAIN-EXTREME 20  
  
  ;; default shapes for all breeds  
  set-default-shape waves "line"  
  set-default-shape raindrops "dot"  
  set-default-shape plants "plant"  
  set-default-shape trees "tree"  
  set-default-shape hpcs "computer server"  
end  
  
to setup  
  clear-all  
  initialize-constants  
  
  ;; river and river bank setup  
  draw-river  
  draw-river-banks  
  
  ;; trees and forest floor  
  initialize-trees  
  draw-forest-floor  
  
  ;; first day of the simulation is arbitrarily the election day !  
  output-print (word  "1/1/" initial-year " ELECTION_DAY")  
  
  reset-ticks  
end  
  
to draw-river  
  ;; initial river-level is 1 meter high (1000 mm)  
  set river-level-previous 1000  
  set river-level-current 1000  
  
  ;; blue patch for the river. x coordinate [-16..-12]  
  ask patches with [pxcor >= -16 and pxcor <= -12] [ set pcolor 97 ]  
  
  ;; decorate the river with some waves (purely decorative)  
  create-waves 35 [  
    setxy (-15 + random 3) random-ycor  
    set color blue  
    set size 1  
    set heading 0  
  ]  
end  
  
to draw-river-banks ;; x [-11..-9]  
  ask patches with [pxcor = -11 or pxcor = -10] [ set pcolor 59 ]  
end  
  
to initialize-trees  
  ;; populate the forest with 1 000 trees  
  create-trees 1000 [  
    setxy (-9 + random 26) random-ycor  
    set color green  
    set size 1  
  ]  
  ;; output-print (word  "1/1/" initial-year " 1 000 trees in the forest")  
end  
  
to draw-forest-floor  
  ;; x coordinates of the forest is in range [-8 .. +16]  
  ask patches with [pxcor >= -9] [  
    let tree-density count trees in-radius 1  
    if tree-density >= 3 [  
      set pcolor green + 2  ; vert foncé  
    ]  
    if tree-density < 3 [  
      set pcolor green + 4  ; vert clair  
    ]  
  
  ]  
end  
  
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
;;;;;;;;;;;;;;;; EVENTS ;;;;;;;;;;;;;;;;  
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
to install-hpc  
  
  if count hpcs = 0 [  
    let px random 10  
    let py random 10  
    let tree-count-before-hpc count trees  
    ask trees with [distancexy px py <= 7] [  
      die  
    ]  
  
    ask trees with [xcor <= px and (ycor >= py - 5 and ycor <= py + 5)] [  
      die  
    ]  
    let tree-count-after-hpc count trees  
  
    draw-forest-floor  
  
    create-hpcs 1 [  
      setxy px py  
      set color magenta  
      set size 8  
    ]  
    output-print (word current-date-full-int " HPC_INSTALLATION ")  
    output-print (word current-date-full-int " FOREST_CUT (" (tree-count-before-hpc - tree-count-after-hpc) " trees cut)")  
  ]  
end  
  
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
;;;;;;;;;;;;;; GO ;;;;;;;;;;;;;;  
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;  
to go  
  compute-today  
  
  ;; river-waves-decoration (useless just for pretty printing)  
  decorate-river  
  
  ;; probability of raining in Luxembourg  
  simulate-event-rain  
  
  ;; rain run-off (from right to left)  
  simulate-rain-run-off  
  
  ;; rain soil absorption  
  simulate-rain-absorption-soil  
  
  ;; rain river absorption  
  simulate-rain-absorption-river  
  
  ;; river-flow decrease overtime  
  simulate-river-level-decrease  
  
  ;; simulate countdown to next-election  
  simulate-next-election  
  
  set total-current-rain sum [quantity] of raindrops  
  
  ;; advances one tick, i.e. one day  
  tick  
end  
  
  
to compute-today  
  let day-of-year ticks mod 360  
  let month-index floor (day-of-year / 30)  
  set current-month item month-index month-names  
  
  set current-day 1 + (ticks mod 30)  
  let year-index floor (ticks / 360)  
  set current-year 2025 + year-index  
  
  set current-date-full-string (word current-day " " current-month " " current-year)  
  set current-date-full-int (word current-day "/" (month-index + 1) "/" current-year)  
  
end  
  
to simulate-event-rain  
  if random-float 1 < 0.5 [  ; 50% chance of rain  
  
    let roll random-float 1  
    if roll < 0.65 [ set rain-intensity "light" ]  
    if roll >= 0.65 and roll < 0.90 [ set rain-intensity "moderate" ]  
    if roll >= 0.90 and roll < 0.98 [ set rain-intensity "heavy" ]  
    if roll > 0.98 [  
      set rain-intensity "extreme"  
      output-print (word current-date-full-int " RAIN_EXTREME")  
    ]  
  
    show (word rain-intensity " rain")  
  
    if rain-intensity = "light"    [ set rain-amount RAIN-LIGHT ]  
    if rain-intensity = "moderate" [ set rain-amount RAIN-MODERATE ]  
    if rain-intensity = "heavy"    [ set rain-amount RAIN-HEAVY ]  
    if rain-intensity = "extreme"  [ set rain-amount RAIN-EXTREME ]  
  
    ask patches [  
      sprout-raindrops 1 [  
        set color blue  
        set size 1  
        set quantity rain-amount  
        let p patch-here  
        if any? trees-on p and [pcolor] of p = green + 4 [     ;; vert-clair -> absorption =  
          set quantity quantity - (2 + random 3)               ;; absoprtion [2..5] mm  
        ]  
        if any? trees-on p and [pcolor] of p = green + 2 [     ;; vert-foncé -> absorption ++  
          set quantity quantity - (5 + random 5)               ;; absoprtion [5..10] mm  
        ]  
    ]  
    ]  
    set total-current-rain sum [quantity] of raindrops  
  ]  
end  
  
to decorate-river  
  ask waves [  
    set ycor ycor + 0.5  
  ]  
end  
  
to simulate-rain-run-off  
  ask raindrops [  
    let p patch-here  
  
    ;; no trees. no soil-absorption. fastrun-off  
    if not any? trees-on p [  
      set xcor xcor - 3  
    ]  
  
    ;; low-density forest. average soil-absorption. average run-off  
    if [pcolor] of p = green + 4 [  
      set quantity quantity * 0.5  
      set xcor xcor - 2  
    ]  
  
    ;; high-density forest. high soil-absorption. slow run-off  
    if [pcolor] of p = green + 2 [  
      set quantity quantity * 0.25  
      set xcor xcor - 1  
    ]  
  ]  
end  
  
to simulate-rain-absorption-soil  
  ask raindrops with [ floor ((quantity * 10) / 10) <= 0] [die]  
end  
  
  
to simulate-rain-absorption-river  
    ask raindrops with [ xcor <= -12] [  
    set river-level-current river-level-current + quantity  
    die  
  ]  
end  
  
to simulate-river-level-decrease  
  set river-level-current river-level-current * 0.95  ;  
  if river-level-current < 0 [ set river-level-current 0 ]  
  
  if river-level-current > 2500 and river-level-previous <= 2500 [  
    output-print (word current-date-full-int " RIVER_FLOOD")  
  ]  
  
  if river-level-current < 500 and river-level-previous >= 500 [  
    output-print (word current-date-full-int " RIVER_DROUGHT")  
  ]  
  
  set river-level-previous river-level-current  
end  
  
to simulate-next-election  
  set town-hall-next-election town-hall-next-election - 1  
  if town-hall-next-election <= 0 [  
    set town-hall-next-election 6 * 360  
    output-print (word current-date-full-int " ELECTION_DAY")  
  ]  
end