directed-link-breed [active-links active-link]
directed-link-breed [inactive-links inactive-link]

turtles-own [ val new-val ] ; a node's past and current quantity, represented as size
links-own [ current-flow ]  ; the amount of quantity that has passed through a link
                            ; in a given step

globals [
  total-val                 ; total quantity in the system
  max-val                   ; maximum quantity held by a single node in the system
  max-flow                  ; maximum quantity that has passed through a link in the system
  mean-flow                 ; average quantity that is passing through an arbitrary
                            ; link in the system
]

;;;;;;;;;;;;;;;;;;;;;;;;
;;; Setup Procedures ;;;
;;;;;;;;;;;;;;;;;;;;;;;;

to setup
  clear-all
  set-default-shape turtles "circle"
  set-default-shape links "small-arrow-link"
  ; create the grid of nodes
  ask patches with [abs pxcor < (grid-size / 2) and abs pycor < (grid-size / 2)]
    [ sprout 1 [ set color blue ] ]

  ; create a directed network such that each node has a LINK-CHANCE percent chance of
  ; having a link established from a given node to one of its neighbors
  ask turtles [
    set val 1
    let neighbor-nodes turtle-set [turtles-here] of neighbors4
    create-active-links-to neighbor-nodes
    [
      set current-flow 0
      if random-float 100 > link-chance
      [
        set breed inactive-links
        hide-link
      ]
    ]
  ]
  ; spread the nodes out
  ask turtles [
    setxy (xcor * (max-pxcor - 1) / (grid-size / 2 - 0.5))
          (ycor * (max-pycor - 1) / (grid-size / 2 - 0.5))
  ]
  update-globals
  update-visuals
  reset-ticks
end

;;;;;;;;;;;;;;;;;;;;;;;
;;; Main Procedure  ;;;
;;;;;;;;;;;;;;;;;;;;;;;

to go
  ask turtles [ set new-val 0 ]
  ask turtles [
    let recipients out-active-link-neighbors
    ifelse any? recipients [
      let val-to-keep val * (1 - diffusion-rate / 100)
      ; we keep some amount of our value from one turn to the next
      set new-val new-val + val-to-keep
      ; What we don't keep for ourselves, we divide evenly among our out-link-neighbors.
      let val-increment ((val - val-to-keep) / count recipients)
      ask recipients [
        set new-val new-val + val-increment
        ask in-active-link-from myself [ set current-flow val-increment ]
      ]
    ] [
      set new-val new-val + val
    ]
  ]
  ask turtles [ set val new-val ]
  update-globals
  update-visuals
  tick
end

to rewire-a-link
  if any? active-links [
    ask one-of active-links [
      set breed inactive-links
      hide-link
    ]
    ask one-of inactive-links [
      set breed active-links
      show-link
    ]
  ]
end

;;;;;;;;;;;;;;;;;;;;;;;
;;;     Updates     ;;;
;;;;;;;;;;;;;;;;;;;;;;;

to update-globals
  set total-val sum [ val ] of turtles
  set max-val max [ val ] of turtles
  if any? active-links [
    set max-flow max [current-flow] of active-links
    set mean-flow mean [current-flow] of active-links
  ]
end

to update-visuals
  ask turtles [ update-node-appearance ]
  ask active-links [ update-link-appearance ]
end

to update-node-appearance ; node procedure
  ; scale the size to be between 0.1 and 5.0
  set size 0.1 + 5 * sqrt (val / total-val)
end

to update-link-appearance ; link procedure
  ; scale color to be brighter when more value is flowing through it
  set color scale-color gray (current-flow / (2 * mean-flow + 0.00001)) -0.4 1
end


; Copyright 2008 Uri Wilensky.
; See Info tab for full copyright and license.