local Vector = {}
Vector.__index = Vector

function Vector.new(x: number, y: number)
    return setmetatable({x = x, y = y}, Vector)
end

function Vector:magnitude(): number
    return math.sqrt(self.x * self.x + self.y * self.y)
end

function Vector.__add(a, b)
    return Vector.new(a.x + b.x, a.y + b.y)
end

function Vector.__tostring(v)
    return `({v.x}, {v.y})`
end

local v1 = Vector.new(3, 4)
local v2 = Vector.new(1, 2)
local v3 = v1 + v2
print(v1:magnitude())
print(tostring(v3))
