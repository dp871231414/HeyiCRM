package com.heyi.modules.system.biz;

import com.heyi.modules.system.manager.SysDictManager;
import com.heyi.modules.system.service.SysDictService;
import com.heyi.publics.common.annotation.DynamicUserFields;
import com.heyi.publics.common.cache.CacheService;
import com.heyi.publics.common.exception.BizException;
import com.heyi.publics.common.util.CopyUtil;
import com.heyi.publics.common.util.IdUtil;
import com.heyi.publics.entity.SysDict;
import com.heyi.publics.entity.form.SysDictSaveForm;
import com.heyi.publics.entity.vo.SysDictVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.List;

@Service
@RequiredArgsConstructor
public class SysDictBiz {

    private final SysDictService sysDictService;
    private final SysDictManager sysDictManager;
    private final CacheService cacheService;

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public SysDict create(SysDictSaveForm form) {
        SysDict po = CopyUtil.copy(form, SysDict::new);
        po.setId(IdUtil.nextId());
        po.setDeletedAt(0L);
        sysDictService.save(po);
        sysDictManager.replaceValues(po.getId(), form.getValues());
        evictCache(po.getCode());
        return po;
    }

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public SysDict update(Long id, SysDictSaveForm form) {
        SysDict po = sysDictService.getById(id);
        if (po == null) {
            throw new BizException("字典不存在");
        }
        po.setName(form.getName());
        po.setCode(form.getCode());
        sysDictService.updateById(po);
        sysDictManager.replaceValues(id, form.getValues());
        evictCache(po.getCode());
        return po;
    }

    @Transactional(rollbackFor = Exception.class)
    public void remove(Long id) {
        SysDict po = sysDictService.getById(id);
        if (po == null) {
            throw new BizException("字典不存在");
        }
        po.setDeletedAt(System.currentTimeMillis());
        sysDictService.updateById(po);
        sysDictManager.replaceValues(id, null);
        evictCache(po.getCode());
    }

    public SysDictVO buildVO(SysDict po) {
        SysDictVO vo = CopyUtil.copy(po, SysDictVO::new);
        vo.setValues(sysDictManager.selectValues(po.getId()));
        return vo;
    }

    /** 按 code 取枚举值（供车型等下拉使用）。结果缓存到 Redis，字典变更时失效。 */
    @SuppressWarnings("unchecked")
    public List<String> valuesByCode(String code) {
        String cacheKey = cacheService.key("dict", "values", code);
        List<String> cached = cacheService.get(cacheKey, List.class);
        if (cached != null) {
            return cached;
        }
        SysDict dict = sysDictManager.selectByCode(code);
        List<String> values = dict == null ? List.of() : sysDictManager.selectValues(dict.getId());
        cacheService.set(cacheKey, values, Duration.ofMinutes(30));
        return values;
    }

    /** 字典变更：清除该字典相关缓存 */
    private void evictCache(String code) {
        if (code != null && !code.isEmpty()) {
            cacheService.delete(cacheService.key("dict", "values", code));
        }
    }
}
