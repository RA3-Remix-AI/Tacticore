#pragma once
#include "near_target.h"
#include "near_weapon.h"
#include <memory>

namespace tacticore::runtime::near_combat {
// No public constructor or caller-provided "reviewed" bit. The Windows factory
// verifies the current game image, process lifetime and fixed artifact/source
// hashes. Read-only handles keep those exact files locked for this lifetime.
// This is a source/build policy; it does not itself grant control or attack.
class NearBuildPolicy final:public TemplatePolicy,public WeaponPolicy {
    struct Files;std::unique_ptr<Files> files_;Binding binding_{};
    NearBuildPolicy(Binding,std::unique_ptr<Files>);
public:
    ~NearBuildPolicy()override;
    NearBuildPolicy(const NearBuildPolicy&)=delete;
    NearBuildPolicy& operator=(const NearBuildPolicy&)=delete;
    static std::unique_ptr<NearBuildPolicy> verify_current_game(Binding,const wchar_t* mod,
        const wchar_t* visibility_capability,const wchar_t* template_source_audit);
    bool reviewed(const Binding&,uint32_t template_pointer,uint32_t type_hash)const override;
    float reviewed_range(const Binding&,uint32_t actor_type_hash,uint32_t weapon_asset)const override;
};
}
