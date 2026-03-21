
#include <string>

#include "Luau/BuiltinDefinitions.h"
#include "Luau/Common.h"
#include "Luau/Frontend.h"
#include "Luau/ModuleResolver.h"
#include "Luau/Parser.h"

LUAU_FASTINT(LuauTypeInferRecursionLimit)
LUAU_FASTINT(LuauTypeInferTypePackLoopLimit)
LUAU_FASTFLAG(LuauSolverV2)


struct FuzzFileResolver : Luau::FileResolver
{
    std::string source;

    std::optional<Luau::SourceCode> readSource(const Luau::ModuleName& name) override
    {
        return Luau::SourceCode{source, Luau::SourceCode::Module};
    }

    std::optional<Luau::ModuleInfo> resolveModule(const Luau::ModuleInfo* context, Luau::AstExpr* node) override
    {
        return std::nullopt;
    }

    std::string getHumanReadableModuleName(const Luau::ModuleName& name) const override
    {
        return name;
    }
};

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* Data, size_t Size)
{
    FInt::LuauTypeInferRecursionLimit.value = 100;
    FInt::LuauTypeInferTypePackLoopLimit.value = 100;
    FFlag::LuauSolverV2.value = true;

    static FuzzFileResolver fileResolver;
    static Luau::NullConfigResolver configResolver;
    static Luau::Frontend frontend{&fileResolver, &configResolver};
    static int once = (Luau::registerBuiltinGlobals(frontend, frontend.globals, false), 1);
    (void)once;

    static int once2 = (Luau::freeze(frontend.globals.globalTypes), 1);
    (void)once2;

    fileResolver.source = std::string(reinterpret_cast<const char*>(Data), Size);

    try

    {
        frontend.check("fuzz");
    }
    catch (std::exception&)
    {
    }
    frontend.clear();

    return 0;
}
