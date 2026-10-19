package com.heyi.modules.system.controller;

import com.heyi.modules.system.biz.RoleBiz;
import com.heyi.modules.system.service.RoleService;
import com.heyi.publics.common.base.SuperController;
import com.heyi.publics.common.result.R;
import com.heyi.publics.entity.Role;
import com.heyi.publics.entity.form.RoleSaveForm;
import com.heyi.publics.entity.vo.RoleVO;
import com.heyi.publics.util.JsonUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/v1/roles")
@RequiredArgsConstructor
public class RoleController extends SuperController<RoleService, Role> {

    private final RoleService roleService;
    private final RoleBiz roleBiz;

    @Override
    protected RoleService service() {
        return roleService;
    }

    @GetMapping("/vo-list")
    public R<List<RoleVO>> voList() {
        List<Role> roles = roleService.list(notDeleted());
        List<RoleVO> vos = new ArrayList<>();
        for (Role role : roles) {
            RoleVO vo = new RoleVO();
            vo.setId(role.getId());
            vo.setName(role.getName());
            vo.setDescription(role.getDescription());
            vo.setScope(role.getScope());
            vo.setPermissions(JsonUtil.readList(role.getPermissions()));
            vo.setIsSystem(role.getIsSystem());
            vos.add(vo);
        }
        return R.ok(vos);
    }

    @PostMapping("/save")
    public R<Role> save(@RequestBody @Validated RoleSaveForm form) {
        return R.ok(roleBiz.create(form));
    }

    @PostMapping("/update")
    public R<Role> update(@RequestParam Long id, @RequestBody @Validated RoleSaveForm form) {
        return R.ok(roleBiz.update(id, form));
    }

    @PostMapping("/delete")
    public R<Boolean> delete(@RequestParam Long id) {
        roleBiz.remove(id);
        return R.ok(true);
    }
}
