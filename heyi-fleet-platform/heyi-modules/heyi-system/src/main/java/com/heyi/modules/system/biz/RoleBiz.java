package com.heyi.modules.system.biz;

import com.heyi.modules.system.manager.RoleManager;
import com.heyi.modules.system.manager.SysDictManager;
import com.heyi.modules.system.manager.UserManager;
import com.heyi.modules.system.service.RoleService;
import com.heyi.publics.common.annotation.DynamicUserFields;
import com.heyi.publics.common.exception.BizException;
import com.heyi.publics.common.util.CopyUtil;
import com.heyi.publics.common.util.IdUtil;
import com.heyi.publics.entity.Role;
import com.heyi.publics.entity.form.RoleSaveForm;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class RoleBiz {

    private final RoleService roleService;
    private final RoleManager roleManager;
    private final SysDictManager sysDictManager;
    private final UserManager userManager;

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public Role create(RoleSaveForm form) {
        if (roleManager.existsName(form.getName(), null)) {
            throw new BizException("角色名称已存在");
        }
        Role po = CopyUtil.copy(form, Role::new);
        po.setId(IdUtil.nextId());
        po.setPermissions(sysDictManager.toJson(form.getPermissions()));
        po.setScope(form.getScope() == null ? "self" : form.getScope());
        po.setIsSystem(0);
        po.setDeletedAt(0L);
        roleService.save(po);
        return po;
    }

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public Role update(Long id, RoleSaveForm form) {
        Role po = roleService.getById(id);
        if (po == null) {
            throw new BizException("角色不存在");
        }
        if (roleManager.existsName(form.getName(), id)) {
            throw new BizException("角色名称已存在");
        }
        po.setName(form.getName());
        po.setDescription(form.getDescription());
        po.setScope(form.getScope());
        po.setPermissions(sysDictManager.toJson(form.getPermissions()));
        roleService.updateById(po);
        return po;
    }

    /** 内置角色、或角色下仍有账号时不可删除 */
    @Transactional(rollbackFor = Exception.class)
    public void remove(Long id) {
        Role po = roleService.getById(id);
        if (po == null) {
            throw new BizException("角色不存在");
        }
        if (po.getIsSystem() != null && po.getIsSystem() == 1) {
            throw new BizException("内置角色不可删除");
        }
        if (userManager.countByRole(id) > 0) {
            throw new BizException("该角色下存在账号，不能删除");
        }
        po.setDeletedAt(System.currentTimeMillis());
        roleService.updateById(po);
    }
}
