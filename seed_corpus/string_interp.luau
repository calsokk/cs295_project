local name = "world"
local greeting = `Hello, {name}!`
print(greeting)

local x = 42
local y = 3.14
print(`x={x}, y={y}, sum={x + y}`)

local t = {a = 1}
print(`table.a = {t.a}`)

local function fmt(val: number): string
    return `value is {val}`
end
print(fmt(100))

local nested = `outer {`inner {1 + 2}`}`
