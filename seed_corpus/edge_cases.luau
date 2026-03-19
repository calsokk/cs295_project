-- Empty constructs
local function empty() end
local t = {}
do end

-- Deeply nested expressions
local x = ((((((1 + 2) * 3) - 4) / 5) % 6) ^ 7)

-- Long string literals
local s = [[
This is a long string
that spans multiple lines
with no escape processing
]]

local s2 = [==[
This uses level 2 long brackets
]==]

-- Max/min numbers
local big = 1e308
local small = 5e-324
local hex = 0xFF
local hex_float = 0x1.fp10
local binary = 0b1010

-- Chained method calls
local result = tostring(math.floor(math.abs(-3.7)))

-- Multiple returns
local function multi()
    return 1, "two", true
end
local a, b, c = multi()

-- Semicolons (optional in Luau)
local q = 1; local w = 2; local e = 3;
