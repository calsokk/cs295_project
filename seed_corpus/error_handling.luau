local ok, err = pcall(function()
    error("something went wrong")
end)
print(ok, err)

local ok2, result = pcall(function()
    return 42
end)
print(ok2, result)

local ok3, msg = xpcall(function()
    error("test error")
end, function(err)
    return "caught: " .. tostring(err)
end)
print(ok3, msg)

local function risky(x: number)
    if x < 0 then
        error(`invalid value: {x}`)
    end
    return math.sqrt(x)
end

local s, v = pcall(risky, -1)
print(s, v)
