turtles-own [
  x-pos  ;; x-pos, y-pos, and z-pos are the cartesian coordinates
  y-pos  ;; don't confuse them with xcor and ycor, which are predefined
  z-pos  ;;   NetLogo variables for turtles
  p      ;; p, theta, and phi are the spherical coordinates
  theta
  phi
 ]

to setup
  clear-all
  set-default-shape turtles "circle"
end

to setup-sphere
  setup
  ;; generate a sphere of radius SHAPE-SIZE
  create-turtles num-turtles
  [
    set p shape-size            ; all points are equal distance from the center
    set theta random-float 360  ; however, random distribution on the surface of the sphere
    set phi random-float 180
    render-turtle
  ]
  reset-ticks
end

; a filled 3D cube
to setup-cube-filled
  setup
  ;; generate a square with edge of length radius
  ;; placing a point randomly anywhere inside the square
  create-turtles num-turtles
  [
    cartesian ((- shape-size) + 2 * (random-float shape-size))
              ((- shape-size) + 2 * (random-float shape-size))
              ((- shape-size) + 2 * (random-float shape-size))
    render-turtle
  ]
  reset-ticks
end

; cube with turtles only on its surface
to setup-cube-surface
  setup
  create-turtles num-turtles
  [
    let temp-alpha shape-size * (1 - 2 * (random 2))   ; +-shape-size
    ; random distribution bounded by +-shape-size
    let temp-beta shape-size - 2 * (random-float shape-size)
    let temp-gamma (random 2)                          ; front/back or left/right?
    ifelse temp-gamma = 0                              ; generate front & back surfaces
    [
      cartesian (temp-alpha)
                (temp-beta)
                (shape-size - (2 * (random-float shape-size)))
    ]
    [
      cartesian (temp-beta)                             ; generating the side surfaces
                (temp-alpha)
                (shape-size - (2 * (random-float shape-size)))
    ]
    render-turtle
  ]
  reset-ticks
end


; 3D cone
to setup-cone
  setup
  create-turtles num-turtles
  [
    set theta (random-float 360)        ; points have a random angle
    set p (random-float shape-size)
    cartesian (p * (cos theta))     ; x = r*cos(theta)
              (p * (sin theta))     ; y = r*sin(theta)
              (shape-size - 2 * p)  ; this centers the cone at the origin
                                   ; instead of it only being in positive space
    render-turtle
  ]
  reset-ticks
end

; vertical cylinder
to setup-cylinder-v
  setup
  ;the code is almost the same as the setup-cone code
  ;except the xy-plane radius remains constant
  create-turtles num-turtles
  [
    let temp-alpha (random 3) - 1         ; which surface (left, right, or body?)
    set theta (random-float 360)
    ifelse temp-alpha = 0
    [
      cartesian (shape-size * (cos theta))
                (shape-size * (sin theta))
                ((- shape-size) + 2 * (random-float shape-size))
    ]
    [
      cartesian ((random-float shape-size) * (cos theta))
                ((random-float shape-size) * (sin theta))
                (temp-alpha * shape-size)
    ]
    render-turtle
  ]
  reset-ticks
end

; horizontal cylinder
to setup-cylinder-h
  setup
  ;generates a cylinder in a horizontal position with capped ends
  create-turtles num-turtles
  [
    let temp-alpha (random 3) - 1      ; which surface (left, right, or body?)
    set theta (random-float 360)
    ifelse temp-alpha = 0              ; generating the actual cylinder
    [
      cartesian ((- shape-size) + 2 * (random-float shape-size))
                (shape-size * (cos theta))
                (shape-size * (sin theta))
    ]
    [
      cartesian (temp-alpha * shape-size)
                ((random-float shape-size) * (cos theta))
                ((random-float shape-size) * (sin theta))
    ]
    render-turtle
  ]
  reset-ticks
end

to setup-pyramid
  setup
  create-turtles num-turtles
  [
    let temp-alpha (- shape-size) + 2 * (random-float shape-size)  ; z coordinate
    set theta (random 2)                         ; front/back or side?
    let temp-beta (shape-size - temp-alpha) / 2
    let temp-gamma -1 + 2 * (random 2)           ; left/right or front/back (-1 or 1)
    ifelse theta = 0
    [
      cartesian (temp-beta * temp-gamma)          ;  left & right surfaces
                ((- temp-beta) + 2 * (random-float temp-beta))
                (temp-alpha)
    ]
    [
      cartesian ((- temp-beta) + 2 * (random-float temp-beta)) ;  front & back surfaces
                (temp-beta * temp-gamma)
                (temp-alpha)
    ]
    render-turtle
  ]
  reset-ticks
end

;; convert from cartesian to spherical coordinates
to cartesian [x y z]
  set p sqrt((x ^ 2) + (y ^ 2) + (z ^ 2))
  set phi (atan sqrt((x ^ 2) + (y ^ 2)) z)
  set theta (atan y x)
end

to go
  ; rotate-turtles on z axis
  ask turtles
  [
    set theta (theta + theta-velocity) mod 360  ; increment angle to simulate rotation
    render-turtle
  ]
  tick
end

to render-turtle
  calculate-turtle-position
  set-turtle-position
end

;; convert from spherical to cartesian coordinates
to calculate-turtle-position
  set y-pos p * (sin phi) * (sin theta)
  set x-pos p * (sin phi) * (cos theta)
  set z-pos p * (cos phi)
end

;; set the turtle's position and color
to set-turtle-position
  ifelse view = "side"                                     ; sideview
  [
    setxy x-pos z-pos
    set color scale-color display-color y-pos (- shape-size) shape-size
  ]
  [
    ifelse view = "top"                                  ; topview
    [
      setxy x-pos y-pos
      set color scale-color display-color z-pos (- shape-size) shape-size
    ]
    [
      setxy (p * (sin phi) * (cos theta))              ; bottomview
            (- (p * (sin phi) * (sin theta)))
      set color scale-color display-color (- z-pos) (- shape-size) shape-size
    ]
  ]
end


; Copyright 1998 Uri Wilensky.
; See Info tab for full copyright and license.