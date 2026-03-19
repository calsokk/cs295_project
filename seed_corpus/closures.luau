local function outer()
    local count = 0
    return function()
        count = count + 1
        return count
    end
end

local counter = outer()
print(counter())
print(counter())
print(counter())

local function make_adder(n)
    return function(x)
        return x + n
    end
end

local add5 = make_adder(5)
print(add5(10))

local function varargs(...)
    local args = {...}
    for i, v in ipairs(args) do
        print(i, v)
    end
    return #args
end

varargs(1, "two", true, nil)
