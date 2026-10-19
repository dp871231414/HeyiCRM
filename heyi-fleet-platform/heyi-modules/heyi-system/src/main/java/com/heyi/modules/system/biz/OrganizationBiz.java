package com.heyi.modules.system.biz;

import com.heyi.modules.system.manager.OrganizationManager;
import com.heyi.modules.system.manager.UserManager;
import com.heyi.modules.system.service.OrganizationService;
import com.heyi.publics.common.annotation.DynamicUserFields;
import com.heyi.publics.common.exception.BizException;
import com.heyi.publics.common.util.CopyUtil;
import com.heyi.publics.common.util.IdUtil;
import com.heyi.publics.entity.Organization;
import com.heyi.publics.entity.form.OrganizationSaveForm;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
public class OrganizationBiz {

    private final OrganizationService organizationService;
    private final OrganizationManager organizationManager;
    private final UserManager userManager;

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public Organization create(OrganizationSaveForm form) {
        Long parentId = form.getParentId() == null ? 0L : form.getParentId();
        if (organizationManager.existsSameLevelName(form.getName(), parentId, null)) {
            throw new BizException("同级下已存在同名部门");
        }
        Organization po = CopyUtil.copy(form, Organization::new);
        po.setId(IdUtil.nextId());
        po.setParentId(parentId);
        po.setType(form.getType() == null ? "dept" : form.getType());
        po.setDeletedAt(0L);
        organizationService.save(po);
        return po;
    }

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public Organization update(Long id, OrganizationSaveForm form) {
        Organization po = organizationService.getById(id);
        if (po == null) {
            throw new BizException("部门不存在");
        }
        if (organizationManager.existsSameLevelName(form.getName(), po.getParentId(), id)) {
            throw new BizException("同级下已存在同名部门");
        }
        po.setName(form.getName());
        po.setHead(form.getHead());
        po.setSortOrder(form.getSortOrder());
        organizationService.updateById(po);
        return po;
    }

    /**
     * 删除约束：部门下有账号、或有下级部门时禁止删除（仅可修改）。
     */
    @Transactional(rollbackFor = Exception.class)
    public void remove(Long id) {
        Organization po = organizationService.getById(id);
        if (po == null) {
            throw new BizException("部门不存在");
        }
        if (organizationManager.hasChildren(id)) {
            throw new BizException("该部门存在下级部门，不能删除");
        }
        if (userManager.countByDept(id) > 0) {
            throw new BizException("该部门下存在账号，不能删除");
        }
        po.setDeletedAt(System.currentTimeMillis());
        organizationService.updateById(po);
    }

    /** 组织树：以 parentId 递归向下 */
    public List<Organization> tree(Long parentId) {
        List<Organization> result = new ArrayList<>();
        List<Organization> children = organizationManager.selectByParentId(parentId == null ? 0L : parentId);
        for (Organization child : children) {
            result.add(child);
            result.addAll(tree(child.getId()));
        }
        return result;
    }
}
