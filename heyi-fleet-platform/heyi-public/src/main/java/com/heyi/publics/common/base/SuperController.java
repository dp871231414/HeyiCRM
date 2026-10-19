package com.heyi.publics.common.base;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.heyi.publics.common.result.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;

/**
 * Controller 基类：统一分页 / 列表 / 详情 / 逻辑删除入口，一律按 deleted_at = 0 过滤。
 * 约定：自定义接口使用 @RequestParam，不使用 @PathVariable。
 */
public abstract class SuperController<S extends SuperService<P>, P extends BaseEntity> {

    protected abstract S service();

    protected LambdaQueryWrapper<P> notDeleted() {
        return new LambdaQueryWrapper<P>().apply("deleted_at = 0");
    }

    @GetMapping("/page")
    public R<IPage<P>> page(@RequestParam(defaultValue = "1") long current,
                            @RequestParam(defaultValue = "10") long size) {
        return R.ok(service().page(new Page<>(current, size), notDeleted()));
    }

    @GetMapping("/list")
    public R<List<P>> list() {
        return R.ok(service().list(notDeleted()));
    }

    @GetMapping("/detail")
    public R<P> detail(@RequestParam Long id) {
        return R.ok(service().getOne(notDeleted().eq(BaseEntity::getId, id)));
    }

    /** 逻辑删除：写入毫秒时间戳，不做物理删除 */
    @PostMapping("/remove")
    public R<Boolean> remove(@RequestParam Long id) {
        P po = service().getOne(notDeleted().eq(BaseEntity::getId, id));
        if (po == null) {
            return R.fail("记录不存在");
        }
        po.setDeletedAt(System.currentTimeMillis());
        return R.ok(service().updateById(po));
    }
}
