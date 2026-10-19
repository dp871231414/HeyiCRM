package com.heyi.modules.system.controller;

import com.heyi.modules.system.biz.SysDictBiz;
import com.heyi.modules.system.service.SysDictService;
import com.heyi.publics.common.base.SuperController;
import com.heyi.publics.common.result.R;
import com.heyi.publics.entity.SysDict;
import com.heyi.publics.entity.form.SysDictSaveForm;
import com.heyi.publics.entity.vo.SysDictVO;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/v1/dicts")
@RequiredArgsConstructor
public class SysDictController extends SuperController<SysDictService, SysDict> {

    private final SysDictService sysDictService;
    private final SysDictBiz sysDictBiz;

    @Override
    protected SysDictService service() {
        return sysDictService;
    }

    @GetMapping("/vo-list")
    public R<List<SysDictVO>> voList() {
        List<SysDict> dicts = sysDictService.list(notDeleted());
        List<SysDictVO> vos = new ArrayList<>();
        for (SysDict dict : dicts) {
            vos.add(sysDictBiz.buildVO(dict));
        }
        return R.ok(vos);
    }

    /** 按 code 取枚举值，供车型等下拉使用 */
    @GetMapping("/values")
    public R<List<String>> values(@RequestParam String code) {
        return R.ok(sysDictBiz.valuesByCode(code));
    }

    @PostMapping("/save")
    public R<SysDict> save(@RequestBody @Validated SysDictSaveForm form) {
        return R.ok(sysDictBiz.create(form));
    }

    @PostMapping("/update")
    public R<SysDict> update(@RequestParam Long id, @RequestBody @Validated SysDictSaveForm form) {
        return R.ok(sysDictBiz.update(id, form));
    }

    @PostMapping("/delete")
    public R<Boolean> delete(@RequestParam Long id) {
        sysDictBiz.remove(id);
        return R.ok(true);
    }
}
