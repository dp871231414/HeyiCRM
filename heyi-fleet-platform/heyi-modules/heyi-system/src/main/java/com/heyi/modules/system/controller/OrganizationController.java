package com.heyi.modules.system.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.heyi.modules.system.biz.OrganizationBiz;
import com.heyi.modules.system.service.OrganizationService;
import com.heyi.publics.common.base.SuperController;
import com.heyi.publics.common.result.R;
import com.heyi.publics.entity.Organization;
import com.heyi.publics.entity.form.OrganizationSaveForm;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/organizations")
@RequiredArgsConstructor
public class OrganizationController extends SuperController<OrganizationService, Organization> {

    private final OrganizationService organizationService;
    private final OrganizationBiz organizationBiz;

    @Override
    protected OrganizationService service() {
        return organizationService;
    }

    @GetMapping("/tree")
    public R<List<Organization>> tree(@RequestParam(required = false) Long parentId) {
        return R.ok(organizationBiz.tree(parentId));
    }

    @PostMapping("/save")
    public R<Organization> save(@RequestBody @Validated OrganizationSaveForm form) {
        return R.ok(organizationBiz.create(form));
    }

    @PostMapping("/update")
    public R<Organization> update(@RequestParam Long id, @RequestBody @Validated OrganizationSaveForm form) {
        return R.ok(organizationBiz.update(id, form));
    }

    @PostMapping("/delete")
    public R<Boolean> delete(@RequestParam Long id) {
        organizationBiz.remove(id);
        return R.ok(true);
    }
}
