import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class DateFilterBar extends StatefulWidget {
  final Function(DateTime, DateTime) onDateRangeChanged;

  const DateFilterBar({
    Key? key,
    required this.onDateRangeChanged,
  }) : super(key: key);

  @override
  State<DateFilterBar> createState() => _DateFilterBarState();
}

class _DateFilterBarState extends State<DateFilterBar> {
  int _selectedIndex = 0;
  DateTime? _startDate;
  DateTime? _endDate;

  final List<String> _filters = ['Mês Atual', 'Últimos 7 dias', 'Últimos 30 dias', 'Personalizado'];

  @override
  void initState() {
    super.initState();
    _applyFilter(0);
  }

  void _applyFilter(int index) {
    final now = DateTime.now();
    DateTime start;
    DateTime end = now;

    switch (index) {
      case 0:
        start = DateTime(now.year, now.month, 1);
        break;
      case 1:
        start = now.subtract(const Duration(days: 7));
        break;
      case 2:
        start = now.subtract(const Duration(days: 30));
        break;
      case 3:
        if (_startDate != null && _endDate != null) {
           start = _startDate!;
           end = _endDate!;
        } else {
           start = now; 
        }
        break;
      default:
        start = DateTime(now.year, now.month, 1);
    }

    setState(() {
      _selectedIndex = index;
      _startDate = start;
      _endDate = end;
    });

    widget.onDateRangeChanged(start, end);
  }

  Future<void> _selectCustomDateRange() async {
    final DateTimeRange? picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime(2101),
      initialDateRange: _startDate != null && _endDate != null
          ? DateTimeRange(start: _startDate!, end: _endDate!)
          : null,
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.dark(
              primary: Color(0xFF10B981),
              onPrimary: Colors.white,
              surface: Color(0xFF151D2C),
              onSurface: Color(0xFFF8FAFC),
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() {
        _startDate = picked.start;
        _endDate = picked.end;
      });
      _applyFilter(3);
    }
  }

  String get _dateRangeLabel {
    if (_startDate == null || _endDate == null) return '';
    final DateFormat formatter = DateFormat("dd 'de' MMM/yyyy", 'pt_BR');
    return 'Dia ${DateFormat('dd').format(_startDate!)} a ${formatter.format(_endDate!)}';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF151D2C),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    Icon(Icons.auto_awesome, color: Color(0xFF10B981), size: 14),
                    SizedBox(width: 4),
                    Text(
                      'Diferencial DemBase',
                      style: TextStyle(
                        color: Color(0xFF10B981),
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                _dateRangeLabel,
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(_filters.length, (index) {
                final isSelected = _selectedIndex == index;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: InkWell(
                    onTap: () {
                      if (index == 3) {
                        _selectCustomDateRange();
                      } else {
                        _applyFilter(index);
                      }
                    },
                    borderRadius: BorderRadius.circular(20),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? const Color(0xFF10B981) : Colors.transparent,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: isSelected ? const Color(0xFF10B981) : const Color(0xFF334155),
                        ),
                      ),
                      child: Text(
                        _filters[index],
                        style: TextStyle(
                          color: isSelected ? Colors.white : const Color(0xFFF8FAFC),
                          fontSize: 14,
                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }
}
