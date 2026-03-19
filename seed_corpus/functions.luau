local function add(a: number, b: number): number
    return a + b
end

local function greet(name: string)
    print("Hello, " .. name)
end

local mul = function(x, y) return x * y end

local result = add(1, 2)
greet("world")
print(mul(3, 4))
