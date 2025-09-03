extensions [ sound ]

breed [ trucks truck ]
breed [ cars car ]
breed [ logs a-log ]
breed [ river-turtles river-turtle ]
breed [ pads pad ]
breed [ frogs frog ] ;; These are all the game pieces.

;;;;;;;;;;;;;;;
;; Variables ;;
;;;;;;;;;;;;;;;

globals [
  action            ;; Last button pressed. Prevent the player from moving the frog until the
                    ;; the game is running.  Checks the status of this button every loop.
  dead?             ;; True when no frog lives are left - used to stop the game
  lives             ;; Remaining lives
  level             ;; Current level
  jumps             ;; Current number of jumps
  time-left         ;; Time remaining
  pads-done         ;; Number of frogs that have successfully reached the pads
]

;; In NetLogo, all the breeds are "turtles".  This can be confusing because
;; there are also "turtles" in the game of Frogger -- they swim in the river.
;; To avoid confusion, we call those turtles "river-turtles".

turtles-own [
  speed            ;; The 'time' variable will be initialized to the value of 'speed' after the turtle moves
  time             ;; This keeps track of how many time loops have occurred since the turtle last moved.
                   ;; It actually counts down from 'speed' to zero.  Once it reaches zero, the turtle
                   ;; moves forward one space
]

river-turtles-own [
  dive?            ;; True when the turtle dives
]

;;;;;;;;;;;;;;;;;;;;;;;;
;;; Setup Procedures ;;;
;;;;;;;;;;;;;;;;;;;;;;;;

to startup            ;; Setup is the 'New Game' button, this will setup the game.
  setup
end

to setup              ;; Initializes the game
  clear-all
  set action 0
  set dead? false
  set lives start-lives
  set-default-shape frogs "frog"
  set-default-shape cars "car"
  set-default-shape logs "log"
  set-default-shape river-turtles "turtle"
  set level start-level
  next-level
  reset-ticks
end

to next-level        ;; This will call the appropriate level procedure, where the level is created
  draw-map
  if ( level = 1 )
    [ level-1 ]
  if ( level = 2 )
    [ level-2 ]
  if ( level = 3 )
    [ level-3 ]
  if ( level = 4 )
    [ level-4 ]
  if ( level = 5 )
    [ level-5 ]
  if ( level = 6 )
    [ user-message "Actually, that was the last level.\nPerhaps you should program some more :-)"
      set dead? true]
end

;; This will color the patches to make the grass, road, and river, and creates the frog.
;; The second line causes the grass to be various similar shades of green so it looks
;; more like real grass.

to draw-map
  clear-patches
  clear-turtles
  ask patches
    [ set pcolor scale-color green ((random 500) + 5000) 0 9000 ]
  setup-pads
  ask patches with [pycor <= max-pycor and pycor >= 3]
    [ set pcolor blue ]
  ask patches with [pycor <= -1 and pycor >= -5]
    [ set pcolor gray ]
  set pads-done 0
  create-frogs 1
    [ set color 53
      reset-frog
    ]
end

;; Initializes the frog by setting it to the right patch and facing the right direction

to reset-frog
  setxy 0 min-pycor
  set heading 0
  set jumps 0
  set time-left start-time
end

;; Creates the five pads equally spaced at the top of the board.
;; The second line uses the modulus operation to determine which x-cor
;; is divisible by three.  This is an easy way to have a pad created every
;; three patches.

to setup-pads
  set-default-shape pads "pad"
  ask patches with [pycor = max-pycor and pxcor mod 3 = 0]
    [ sprout-pads 1 ]
end

to create-truck [ x y direction quickness ]   ;; Creates and initializes a truck
  let truck-color (random 13 + 1) * 10 + 3
  ask patches with [(pxcor = x or pxcor = (x + 1)) and pycor = y]
    [ sprout-trucks 1
        [ set color truck-color
          set heading direction
          set speed quickness
          set time speed
          ifelse ((pxcor = x) xor (direction = 90))
            [ set shape "truck" ]
            [ set shape "truck rear" ]
        ]
    ]
end

to create-car [x y direction quickness]     ;; Creates and initializes a car
  create-cars 1
    [ set color (random 13 + 1) * 10 + 3
      setxy x y
      set heading direction
      set speed quickness
      set time speed
    ]
end

;; Creates and initializes a log.

to create-log [x y leng quickness]
  ask patches with [pycor = y and pxcor >= x and pxcor < (x + leng)]
    [ sprout-logs 1
        [ set color brown
          set heading 90
          set speed quickness
          set time speed
        ]
    ]
end

to create-river-turtle [x y leng quickness]    ;; Creates and initializes a river-turtle
  ask patches with [pycor = y and pxcor >= x and pxcor < (x + leng)]
    [ sprout-river-turtles 1
        [ set heading 270
          set speed quickness
          set time speed
          set color 54
          set dive? false
        ]
    ]
end

to make-river-turtle-dive [num]    ;; Causes a random river-turtle(s) to dive underwater.
  repeat num
    [ ask one-of river-turtles with [not dive?]
        [ set dive? true ]
    ]
end


;;;;;;;;;;;;;;;;;;;;;;;;;;
;;; Runtime Procedures ;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;


to go            ;; The main procedure
  if dead?
    [ stop ]
  move
end

;; This is the time loop: every 0.1 seconds it decrements every turtle's 'time'
;; variable and check to see if it should move (when it reaches zero).  It then will
;; reset the 'time' if it is zero.  The logs and river-turtles need their own special
;; procedure to move since they "carry" the frog with them.

to move
  move-frog
  every 0.1
    [ ask turtles
        [ decrement-time ]
      ask turtles with [time = 0.0 and breed != frogs]
        [ set time speed
          ifelse (breed = logs)
            [ move-log ]
            [ ifelse (breed = river-turtles)
                [ move-river-turtle ]
                [ fd 1 ]
            ]
        ]
      check-frog
    ]
  display
end

;; This will decrement the 'time' for all non-frogs and it will decrement the 'time-left'
;; global variable.  The precision function is needed to verify there is only one decimal
;; place on the time variables.

to decrement-time
  ifelse (breed = frogs)
    [ set time-left precision (time-left - 0.1) 1 ]
    [ set time precision (time - 0.1) 1 ]
end

;;  Every time loop, we need to see what the frog's status is (dead, on a pad, etc..)
;;  First it will need to see if it is on a pad and make sure there are no other frogs there
;;  (by checking the shape of the the pad).  Then you need to check to see if the frog is in
;;  a space where he should die.  Finally, it checks to see if the level is complete.

to check-frog
  ask frogs
    [ if any? pads-here with [shape = "pad"]
        [ sound:play-drum "CRASH CYMBAL 2" 97
          ask pads-here
            [ set shape "frog"
              set heading 0
              set color 54
              set pads-done (pads-done + 1)
            ]
          reset-frog
        ]
      if ((any? trucks-here) or (any? cars-here) or (time-left <= 0) or
         ((pcolor = blue) and
          (count pads-here = 0) and
          (count logs-here = 0) and
          (count river-turtles-here with [not hidden?] = 0)))
        [ kill-frog ]
    ]
  if ( pads-done = 5 )
    [ set level (level + 1)
      set pads-done 0
      user-message (word "Congrats, all your frogs are safe!\nOn to level " level "...")
      next-level
    ]
end

to kill-frog        ;; This is called when the frog dies, checks if the game is over
  set lives (lives - 1)
  ifelse (lives = 0)
    [ user-message "Your frog died!\nYou have no more frogs!\nGAME OVER!"
      set dead? true
      die
    ]
    [ user-message (word "Your frog died!\nYou have " lives " frogs left.")
      reset-frog
    ]
end

;; This is a special procedure to move a log.  It needs to move any frogs that
;; are on top of it.

to move-log
  ask frogs-here
    [ if (pxcor != max-pxcor)
        [ set xcor xcor + 1 ]
    ]
  fd 1
end

;; This is a special procedure to move the river-turtles.  It needs to move any frogs that
;; are on top of it.

to move-river-turtle
  fd 1
  ask frogs-at 1 0
    [ set xcor xcor - 1
      if (xcor = max-pxcor)
        [ set xcor xcor + 1 ]
    ]
  dive-river-turtle
end

;; If a river-turtle has been instructed to dive, this procedure will implement that.
;; It will also cause it to splash and rise back up.  It uses a random numbers to
;; determine when it should dive and rise back up.  Theoritically, it will dive about
;; every eighth move and stay down for about five moves, but this isn't always the case
;; (the randomness is added for increasing the challenge of the game)

to dive-river-turtle
  if dive?
    [ ifelse (hidden? and random 5 = 1)
        [ show-turtle ]
        [ if ( shape = "splash" )
            [ set shape "turtle"
              hide-turtle
            ]
          if (shape = "turtle" and random 8 = 1)
            [ set shape "splash" ]
        ]
    ]
end


;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;;; Interface Procedures ;;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;

to move-frog
  if (action != 0)
    [ if (action = 1)
        [ move-left ]
      if (action = 2)
        [ move-right ]
      if (action = 3)
        [ move-down ]
      if (action = 4)
        [ move-up ]
      sound:play-drum "LONG GUIRO" 50
      set action 0
    ]
end

to move-left
  ask frogs with [xcor != min-pxcor]
    [ set heading 270
      fd 1
      set jumps ( jumps + 1 )
    ]
  check-frog
end

to move-right
  ask frogs with [xcor != max-pxcor]
    [ set heading 90
      fd 1
      set jumps ( jumps + 1 )
    ]
  check-frog
end

to move-up
  ask frogs with [ycor != max-pycor]
    [ set heading 0
      fd 1
      set jumps ( jumps + 1 )
    ]
  check-frog
end

to move-down
  ask frogs with [ycor != min-pycor]
    [ set heading 180
      fd 1
      set jumps ( jumps + 1 )
    ]
  check-frog
end


;;;;;;;;;;;;;;
;;; Levels ;;;
;;;;;;;;;;;;;;

to level-1
  create-truck 5 -5 270 .9
  create-truck 0 -5 270 .9
  create-truck -8 -4 90 .9
  create-truck -5 -4 90 .9
  create-truck 2 -4 90 .9
  create-truck -3 -3 270 .8
  create-truck 6 -3 270 .8
  create-car 0 -2 90 .4
  create-car -4 -2 90 .4
  create-car 8 -1 270 .2
  create-car 3 -1 270 .2
  create-log 4 3 3 .6
  create-log -8 3 5 .6
  create-log 4 5 2 .7
  create-log -4 5 3 .7
  create-log 1 7 4 .3
  create-log -6 7 4 .3
  create-river-turtle 2 4 2 .4
  create-river-turtle -4 4 4 .4
  create-river-turtle 5 4 4 .4
  create-river-turtle -3 6 4 .5
  create-river-turtle 7 6 3 .5
end

to level-2
  create-truck 4 -5 270 .8
  create-truck -3 -5 270 .8
  create-truck 0 -4 90 .9
  create-truck -4 -4 90 .9
  create-truck -1 -3 270 .8
  create-truck 4 -3 270 .8
  create-truck -5 -3 270 .8
  create-car 0 -2 90 .2
  create-car -4 -2 90 .2
  create-car 8 -2 90 .2
  create-car 6 -1 270 .4
  create-car 2 -1 270 .4
  create-car -3 -1 270 .4
  create-car -6 -1 270 .4
  create-log 6 3 3 .6
  create-log -4 3 4 .6
  create-log 0 5 3 .3
  create-log -6 5 3 .3
  create-log 1 7 4 .5
  create-log 6 7 4 .5
  create-river-turtle 0 4 4 .3
  create-river-turtle 6 4 4 .3
  create-river-turtle 0 6 4 .4
  create-river-turtle 6 6 3 .4
  make-river-turtle-dive 1
end

to level-3
  create-truck -8 -5 270 .7
  create-truck -4 -5 270 .7
  create-truck 0 -5 270 .7
  create-truck -2 -4 90 .7
  create-truck 2 -4 90 .7
  create-truck -6 -4 90 .7
  create-truck -4 -3 270 .7
  create-truck 0 -3 270 .7
  create-truck 4 -3 270 .7
  create-car -3 -2 90 .2
  create-car -5 -2 90 .2
  create-car 5 -2 90 .2
  create-car 1 -2 90 .2
  create-car 0 -1 270 .3
  create-car 5 -1 270 .3
  create-car -7 -1 270 .3
  create-car -3 -1 270 .3
  create-log -6 3 4 .4
  create-log -2 5 3 .4
  create-log 5 5 3 .4
  create-log -4 7 2 .2
  create-log 0 7 2 .2
  create-log 4 7 2 .2
  create-river-turtle -4 4 4 .3
  create-river-turtle 5 4 4 .3
  create-river-turtle -1 6 3 .4
  create-river-turtle -8 6 3 .4
  make-river-turtle-dive 3
end

to level-4
  create-truck -8 -5 270 .5
  create-truck -2 -5 270 .5
  create-truck 6 -5 270 .5
  create-truck 4 -4 90 .6
  create-truck -1 -4 90 .6
  create-truck -6 -4 90 .6
  create-car -4 -3 270 .3
  create-car 0 -3 270 .3
  create-car 4 -3 270 .3
  create-car 7 -3 270 .3
  create-car -3 -2 90 .2
  create-car -5 -2 90 .2
  create-car 5 -2 90 .2
  create-car 1 -2 90 .2
  create-car 0 -1 270 .3
  create-car 5 -1 270 .3
  create-car -7 -1 270 .3
  create-car -3 -1 270 .3
  create-log -3 3 3 .3
  create-log -3 5 3 .3
  create-log -3 7 3 .3
  create-river-turtle -4 4 4 .3
  create-river-turtle 4 4 4 .3
  create-river-turtle -7 4 1 .3
  create-river-turtle -1 6 3 .4
  create-river-turtle -8 6 3 .4
  create-river-turtle 3 6 2 .4
  make-river-turtle-dive 4
end

to level-5
  create-car -4 -5 270 .3
  create-car 0 -5 270 .3
  create-car 4 -5 270 .3
  create-car 7 -5 270 .3
  create-car -3 -4 90 .2
  create-car -5 -4 90 .2
  create-car 5 -4 90 .2
  create-car 1 -4 90 .2
  create-car 8 -4 90 .2
  create-car -4 -3 270 .3
  create-car 0 -3 270 .3
  create-car 4 -3 270 .3
  create-car 7 -3 270 .3
  create-car -3 -2 90 .2
  create-car -5 -2 90 .2
  create-car 4 -2 90 .2
  create-car 1 -2 90 .2
  create-car 7 -2 90 .2
  create-car 0 -1 270 .3
  create-car 5 -1 270 .3
  create-car -7 -1 270 .3
  create-car -3 -1 270 .3
  create-log -5 3 2 .2
  create-log 0 5 2 .1
  create-log -5 7 2 .2
  create-river-turtle -4 4 2 .3
  create-river-turtle 4 4 3 .3
  create-river-turtle -7 4 2 .3
  create-river-turtle -1 6 2 .3
  create-river-turtle -8 6 2 .3
  create-river-turtle 3 6 3 .3
  make-river-turtle-dive 5
end


; Copyright 2002 Uri Wilensky.
; See Info tab for full copyright and license.